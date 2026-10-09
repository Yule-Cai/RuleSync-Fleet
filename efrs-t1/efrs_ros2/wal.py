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


def wal_read_epoch(path: Path) -> int:
    epoch = 0
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    epoch = max(epoch, int(json.loads(line)["epoch"]))
    except FileNotFoundError:
        pass
    return epoch


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
