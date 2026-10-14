"""T1.2 F1 ledger audit (read-only; records untouched).

Joins each run's MotionFence local ledgers (procs/ledger-R*.jsonl)
against the F1 authorization rules. For every ACCEPT row requires
now <= lease_deadline, required epoch/hash equal to local committed
epoch/hash, and reconciled-and-not-holding.
Also joins motion_event ACCEPTs by cmd_id for 100% ledger coverage
(G6: zero unverifiable ACCEPT).

Usage: python3 ledger_audit.py --procs <procs-dir> --rec <record.json>
Prints one JSON line. Exit 0 always; verdict in "gate_ok".
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=Path, required=True)
    ap.add_argument("--rec", type=Path, required=True)
    args = ap.parse_args()

    rows = []
    ledgers_found = 0
    unreadable = []
    for path in sorted(glob.glob(str(args.procs / "ledger-*.jsonl"))):
        ledgers_found += 1
        try:
            for line in open(path):
                line = line.strip()
                if line:
                    d = json.loads(line)
                    if "decision" in d:
                        rows.append((Path(path).name, d))
        except Exception as e:
            # A missing/corrupt ledger makes the run evidence-incomplete
            # (never PASS) — recorded, never silently skipped.
            unreadable.append(f"{Path(path).name}:{type(e).__name__}")
    accepts = [r for _, r in rows if r.get("decision") == "ACCEPT"]
    bad_expiry = [r for r in accepts
                  if r.get("monotonic_ns") is None
                  or r.get("lease_deadline_monotonic_ns") is None
                  or int(r["monotonic_ns"])
                  > int(r["lease_deadline_monotonic_ns"])]
    bad_epoch = [r for r in accepts
                 if r.get("required_epoch") != r.get("local_committed_epoch")]
    bad_hash = [r for r in accepts
                if r.get("required_hash") != r.get("local_committed_hash")]
    bad_recon = [r for r in accepts
                 if not r.get("reconciled") or r.get("holding")]
    # Coverage: every motion_event ACCEPT must match a ledger ACCEPT row.
    rec = json.load(open(args.rec))
    ev_accepts = [e for e in rec.get("events", [])
                  if e.get("verdict") == "EXECUTED"]
    ledger_cmds = {r.get("cmd_id") for r in accepts}
    uncovered = [e.get("cmd_id") for e in ev_accepts
                 if e.get("cmd_id") not in ledger_cmds]
    out = {"ledgers_found": ledgers_found,
           "unreadable_ledgers": unreadable,
           "ledger_rows": len(rows),
           "accepts": len(accepts),
           "accepted_after_expiry": len(bad_expiry),
           "accepted_epoch_mismatch": len(bad_epoch),
           "accepted_hash_mismatch": len(bad_hash),
           "accepted_while_reconciling": len(bad_recon),
           "event_accepts": len(ev_accepts),
           "unverifiable_accepts": len(uncovered),
           "gate_ok": (not bad_expiry and not bad_epoch and not bad_hash
                       and not bad_recon and not uncovered
                       and not unreadable
                       and ledgers_found > 0)}
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
