"""30-repetition driver: deterministic fault seeds per (fault, rep).

Sequential containers, fresh domain per run. Usage (host):
  python3 fault_harness/rep.py --protocol efrs --fault F6 --reps 30
      --domain-start 210 --outdir experiments/t1_3robot_rep
      --repo-mount /home/gamer/RuleSync-Fleet [--ablation A1]
Aggregates metrics across reps (mean + max; max primary for safety).
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedules import schedules_3robot


def seed_shift(sched: dict, rep: int) -> dict:
    s = copy.deepcopy(sched)
    for f in s.get("faults", []):
        if f["kind"] == "loss_random":
            f["seed"] = int(f.get("seed", 1)) + rep
    return s



def sweep():
    """Kill our leftover ROS stack processes/containers before each run."""
    import shutil
    import time
    subprocess.run(["pkill", "-f", "efrs_ros2/coordinator/coordinator.py"],
                   capture_output=True)
    subprocess.run(["pkill", "-f", "efrs_ros2/robot_agent/robot_agent.py"],
                   capture_output=True)
    subprocess.run(["pkill", "-f", "efrs_ros2/motion_fence/motion_fence.py"],
                   capture_output=True)
    if shutil.which("podman"):
        try:
            out = subprocess.run(
                ["podman", "ps", "--filter", "ancestor=d1-lyrical",
                 "--format", "{{.ID}}"], capture_output=True, text=True,
                timeout=30)
            for cid in out.stdout.split():
                subprocess.run(["podman", "rm", "-f", cid],
                               capture_output=True, timeout=60)
        except Exception:
            pass
    time.sleep(3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--fault", required=True)
    ap.add_argument("--reps", type=int, default=30)
    ap.add_argument("--domain-start", type=int, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--repo-mount", required=True)
    ap.add_argument("--image", default="d1-lyrical")
    ap.add_argument("--ablation", default=None)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    base = dict(schedules_3robot(args.protocol)[args.fault])
    base["protocol"] = args.protocol
    if args.ablation:
        base["ablation"] = args.ablation
    agg = []
    for rep in range(args.reps):
        sweep()
        if (outdir / f"rec-{args.protocol}-{args.fault}-r{rep}.json").exists():
            print(json.dumps({"rep": rep, "skipped": True}), flush=True)
            continue
        sched = seed_shift(base, rep)
        spath = outdir / f"sched-{args.protocol}-{args.fault}-r{rep}.json"
        spath.write_text(json.dumps(sched, indent=1, sort_keys=True))
        rec = outdir / f"rec-{args.protocol}-{args.fault}-r{rep}.json"
        domain = 201 + (rep % 10)
        cmd = ["podman", "run", "--rm", "--shm-size=2g",
               "-v", f"{args.repo_mount}:/ws", "-w", "/ws/efrs-t1",
               "-e", f"ROS_DOMAIN_ID={domain}", args.image, "bash", "-lc",
               "source /opt/ros/lyrical/setup.bash && "
               "/opt/venv/bin/python fault_harness/runner.py "
               f"--schedule /ws/{spath.relative_to(args.repo_mount)} "
               f"--out /ws/{rec.relative_to(args.repo_mount)} "
               f"--domain-id {domain} --repo /ws/efrs-t1 "
               "--python /opt/venv/bin/python"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = rec.exists()
        tail = ""
        if ok:
            try:
                tail = json.dumps(json.load(open(rec))["metrics"])[:220]
            except Exception as e:
                ok = False
                tail = f"record-unreadable: {e}"
        print(json.dumps({"rep": rep, "ok": ok, "tail": tail}), flush=True)
        agg.append({"rep": rep, "ok": ok, "tail": tail})
    (outdir / f"rep-{args.protocol}-{args.fault}.json").write_text(
        json.dumps(agg, indent=1))
    print("REP-DONE", args.protocol, args.fault)


if __name__ == "__main__":
    main()
