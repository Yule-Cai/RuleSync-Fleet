"""30-rep campaign driver: all faults x protocols, resumable.

Skips reps whose record already exists. Usage (host):
  nohup python3 fault_harness/rep_all.py \
      --outdir experiments/t1_3robot_rep \
      --repo-mount /home/gamer/RuleSync-Fleet > /tmp/rep_all.log 2>&1 &
Estimated: 1440 runs x ~25 s ~= 10 h.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

FAULTS = [f"F{i}" for i in range(16)]
PROTOS = ("broadcast", "2pc", "efrs")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--repo-mount", required=True)
    ap.add_argument("--reps", type=int, default=30)
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    total = done = 0
    for p in PROTOS:
        for f in FAULTS:
            have = sum(
                1 for r in range(args.reps)
                if (outdir / f"rec-{p}-{f}-r{r}.json").exists())
            if have == args.reps:
                print(f"SKIP {p} {f} (done)", flush=True)
                continue
            r = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parent
                                     / "rep.py"),
                 "--protocol", p, "--fault", f, "--reps",
                 str(args.reps), "--domain-start", "201", "--outdir",
                 str(outdir), "--repo-mount", args.repo_mount],
                capture_output=True, text=True, timeout=3600)
            print(f"DONE {p} {f} rc={r.returncode}", flush=True)
            total += args.reps
            done += args.reps
    print(f"REP-ALL-DONE {done}/{3 * 16 * args.reps}")


if __name__ == "__main__":
    main()
