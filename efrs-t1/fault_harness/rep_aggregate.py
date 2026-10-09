"""Aggregate 30-rep campaign into gate verdicts (read-only).

Usage: python3 rep_aggregate.py --dir experiments/t1_3robot_rep \
    --out experiments/t1_3robot_rep_agg.json
For each (protocol, fault): n_ok, stale counts, max/mean stale ms,
rollbacks, auth_expired breakdown, reconciliations. EFRS gate row:
max stale vs B_real, any auth_expired with contradictory evidence.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

B_REAL_MS = 1300.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    try:
        from analyze import analyze
    except ImportError:
        from fault_harness.analyze import analyze  # type: ignore

    table: dict = {}
    for p in ("broadcast", "2pc", "efrs"):
        table[p] = {}
        for f in sorted({Path(x).name.split("-")[2]
                         for x in glob.glob(
                             str(Path(args.dir) / f"rec-{p}-*.json"))}):
            rows = []
            for path in sorted(glob.glob(str(Path(args.dir) /
                                             f"rec-{p}-{f}-r*.json"))):
                try:
                    rec = json.load(open(path))
                except Exception as e:
                    rows.append({"rep": path, "unreadable": str(e)[:100]})
                    continue
                g = analyze(rec)
                rows.append({"rep": Path(path).name, "gates": g})
            ok = [r for r in rows if "unreadable" not in r]
            gs = [r["gates"] for r in ok]
            table[p][f] = {
                "n": len(rows),
                "n_ok": len(ok),
                "max_stale_ms": max(
                    [g["fleet_stale_max_ms"] for g in gs] + [0.0]),
                "mean_stale_ms": (sum(g["fleet_stale_max_ms"] for g in gs)
                                  / max(len(gs), 1)),
                "sum_auth_expired": sum(
                    g["authorization_expired_accepts"] for g in gs),
                "sum_contradictory": sum(
                    g["epoch_mismatch_executions"]
                    + g["invalid_lease_executions"]
                    + g["unreconciled_executions"] for g in gs),
                "sum_unverifiable": sum(
                    g["unverifiable_executions"] for g in gs),
                "sum_rollbacks": sum(
                    g["epoch_rollback_count"] for g in gs),
            }
    Path(args.out).write_text(json.dumps(table, indent=1, sort_keys=True))
    efrs_bad = {f: v for f, v in table["efrs"].items()
                if v["max_stale_ms"] > B_REAL_MS
                or v["sum_contradictory"] > 0}
    print(json.dumps({"efrs_faults_over_gate": sorted(efrs_bad),
                      "n_faults": sum(len(v) for v in table.values())},
                     sort_keys=True))


if __name__ == "__main__":
    main()
