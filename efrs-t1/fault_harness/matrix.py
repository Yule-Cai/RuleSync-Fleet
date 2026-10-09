"""Deterministic fault matrix driver: F0-F15 x protocols, sequential.

Writes schedule JSONs + runs runner.py once per (fault, protocol) in a
fresh container with a fresh ROS_DOMAIN_ID. Sequential (one container
at a time). Usage (host):
  python3 fault_harness/matrix.py --protocol efrs --domain-start 210
                                  --outdir experiments/t1_3robot
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedules import schedules_3robot

FAULTS = [f"F{i}" for i in range(16)]



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
    ap.add_argument("--domain-start", type=int, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--faults", default=",".join(FAULTS))
    ap.add_argument("--image", default="d1-lyrical")
    ap.add_argument("--repo-mount", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    scheds = schedules_3robot(args.protocol)
    domain = int(args.domain_start)
    base_domain = domain
    summary = []
    for fname in args.faults.split(","):
        sweep()
        sched = dict(scheds[fname])
        sched["protocol"] = args.protocol
        spath = outdir / f"sched-{args.protocol}-{fname}.json"
        spath.write_text(json.dumps(sched, indent=1, sort_keys=True))
        rec = outdir / f"rec-{args.protocol}-{fname}-det.json"
        csched = f"/ws/{spath.relative_to(args.repo_mount)}"
        crec = f"/ws/{rec.relative_to(args.repo_mount)}"
        cmd = ["podman", "run", "--rm", "--shm-size=2g",
               "-v", f"{args.repo_mount}:/ws", "-w", "/ws/efrs-t1",
               "-e", f"ROS_DOMAIN_ID={domain}", args.image, "bash", "-lc",
               "source /opt/ros/lyrical/setup.bash && "
               "/opt/venv/bin/python fault_harness/runner.py "
               f"--schedule {csched} "
               f"--out {crec} "
               f"--domain-id {domain} --repo /ws/efrs-t1 "
               "--python /opt/venv/bin/python"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        ok = rec.exists()
        line = (r.stdout or "").strip().splitlines()
        summary.append({"fault": fname, "ok": ok,
                        "tail": line[-1][:200] if line else ""})
        print(json.dumps(summary[-1]), flush=True)
        domain = 201 + ((domain - 201 + 1) % 10)
    (outdir / f"matrix-{args.protocol}-det.json").write_text(
        json.dumps(summary, indent=1))
    print("MATRIX-DONE", args.protocol)


if __name__ == "__main__":
    main()
