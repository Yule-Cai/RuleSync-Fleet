"""Durable state: coordinator WAL + robot restart files (stdlib only).

Coordinator WAL: append-only JSONL. Each record fsync'd before the
caller proceeds (the durable linearization point). Restart recovers
the maximum durable epoch (never invents).
Robot file: single JSON blob {committed, hash, fence_seen} rewritten
atomically (tmp + rename) on every commit application.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def wal_append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def wal_commit(path: Path, epoch: int, hash_: str, fence: int) -> None:
    """T1.1: durable commit record (adds t_mono_ns; kind explicit)."""
    import time
    wal_append(path, {"kind": "commit", "epoch": int(epoch),
                      "hash": str(hash_), "fence": int(fence),
                      "t_mono_ns": time.clock_gettime_ns(
                          time.CLOCK_MONOTONIC)})


def wal_abort(path: Path, txn: str, epoch: int, gen: int,
              hash_: str, fence: int, reason: str) -> None:
    """T1.1: durable timeout/reject abort record (distinguishes ABORTED).

    reason ∈ {"timeout", "reject"}. Carries t_mono_ns for heal-to-abort
    attribution in analysis.
    """
    import time
    if reason not in ("timeout", "reject"):
        raise ValueError("abort reason")
    wal_append(path, {"kind": "abort", "txn": str(txn),
                      "epoch": int(epoch), "gen": int(gen),
                      "hash": str(hash_), "fence": int(fence),
                      "reason": reason,
                      "t_mono_ns": time.clock_gettime_ns(
                          time.CLOCK_MONOTONIC)})


def wal_read_epoch(path: Path) -> int:
    # T1.1: abort records carry "epoch" for identification but must NEVER
    # inflate the recovered committed epoch — filter kind == "commit".
    epoch = 0
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    if rec.get("kind", "commit") != "commit":
                        continue
                    epoch = max(epoch, int(rec["epoch"]))
    except FileNotFoundError:
        pass
    return epoch


def wal_read_aborted_gens(path: Path) -> set:
    """T1.1: set of (epoch, gen) terminally aborted (never resurrect)."""
    out = set()
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    if rec.get("kind") == "abort":
                        out.add((int(rec["epoch"]), int(rec["gen"])))
    except FileNotFoundError:
        pass
    return out


def wal_read_proposed_epochs(path: Path) -> list:
    """T1.1: epochs ever proposed (commit or abort records), in order."""
    out = []
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    if rec.get("kind") in ("commit", "abort"):
                        ep = int(rec["epoch"])
                        if ep not in out:
                            out.append(ep)
    except FileNotFoundError:
        pass
    return out


def wal_read_fence(path: Path) -> int:
    fence = 0
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    fence = max(fence, int(rec.get("fence", 0)))
    except FileNotFoundError:
        pass
    return fence


def robot_save(path: Path, committed: int, hash_: str, fence_seen: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"committed": int(committed),
                               "hash": str(hash_),
                               "fence_seen": int(fence_seen)},
                              sort_keys=True))
    os.replace(tmp, path)


def robot_load(path: Path):
    try:
        d = json.loads(Path(path).read_text())
        return int(d["committed"]), str(d["hash"]), int(d["fence_seen"])
    except FileNotFoundError:
        return 0, "h0", 0
