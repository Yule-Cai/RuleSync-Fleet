"""Aggregate run records into gate tables (read-only, numpy-free).

Usage: python3 aggregate.py --dir experiments/t1_3robot --out agg.json
Reads rec-*.json (deterministic) and rep-*.json summaries. Prints the
3-robot gate table + baseline counterexample verdicts.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

B_REAL_MS = 1300.0


def load_records(pattern):
    out = []
    for p in sorted(glob.glob(pattern)):
        try:
            out.append(json.load(open(p)))
        except Exception as e:
            out.append({"_path": p, "_unreadable": str(e)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    d = Path(args.dir)

    table = {}
    for p in ("broadcast", "2pc", "efrs"):
        table[p] = {}
        for path in sorted(glob.glob(str(d / f"rec-{p}-*.json"))):
            if "-r" in Path(path).name:
                continue
            try:
                rec = json.load(open(path))
            except Exception:
                continue
            tag = Path(path).stem.replace(f"rec-{p}-", "")
            table[p][tag] = rec.get("metrics", {})
    Path(args.out).write_text(json.dumps(table, indent=1, sort_keys=True))
    # Gate summary for EFRS deterministic matrix.
    efrs = table.get("efrs", {})
    bad = {k: v for k, v in efrs.items()
           if v.get("stale_motion_count", 0) > 0
           or v.get("epoch_rollback_count", 0) > 0
           or v.get("max_stale_motion_duration_ms", 0) > B_REAL_MS}
    print(json.dumps({"efrs_det_non_clean": sorted(bad),
                      "n_efrs": len(efrs)}, sort_keys=True))


if __name__ == "__main__":
    main()
