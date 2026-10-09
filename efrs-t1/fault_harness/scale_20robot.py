"""20-robot scale run: 100 epoch updates, mixed faults, system metrics.

One long scenario (EFRS only — scale is a cost experiment, not a safety
proof): 20 agents + 20 fences + coordinator in one container, real DDS.
Proposes every 2.5 s x100 with deterministic mixed faults (<=20%
partitioned at once, delay/loss/restart/stale-replay). Podman stats
polled for CPU/RSS/NET; latencies derived post-hoc from the record +
WAL mtimes. No Gazebo (per brief).

Usage (host): python3 fault_harness/scale_20robot.py \
    --outdir experiments/t1_20robot --repo-mount /home/gamer/RuleSync-Fleet
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

N = 20
UPDATES = 100
STEP = 2.5


def build_schedule():
    import random

    rng = random.Random(20)
    robots = [f"R{i}" for i in range(1, N + 1)]
    proposes = [{"t": round(1.5 + i * STEP, 2), "epoch": i + 1}
                for i in range(UPDATES)]
    faults = []
    t = 5.0
    while t < UPDATES * STEP:
        kind = rng.choice(["part", "loss", "delay", "restart", "stale"])
        if kind == "part":
            victims = rng.sample(robots, rng.randint(1, 4))
            faults.append({"t": round(t, 2), "kind": "partition5",
                           "groups": [[v] for v in victims],
                           "until": round(t + rng.uniform(2.0, 5.0), 2)})
        elif kind == "loss":
            faults.append({"t": round(t, 2), "kind": "loss_random",
                           "p": 0.2, "seed": int(t)})
        elif kind == "delay":
            faults.append({"t": round(t, 2), "kind": "delay",
                           "msg_kind": "commit", "ms": 300})
        elif kind == "restart":
            v = rng.choice(robots)
            faults.append({"t": round(t, 2), "kind": "crash_robot",
                           "robot": v, "restart_at": round(t + 3.0, 2)})
        t += rng.uniform(4.0, 9.0)
    return {"protocol": "efrs", "robots": robots,
            "duration_s": UPDATES * STEP + 15.0, "vote_timeout_ms": 1500,
            "proposes": proposes, "faults": faults,
            "motion_plan": "honest"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--repo-mount", required=True)
    ap.add_argument("--image", default="d1-lyrical")
    ap.add_argument("--domain", type=int, default=150)
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    sched = build_schedule()
    (outdir / "sched-scale20.json").write_text(
        json.dumps(sched, indent=1, sort_keys=True))
    print(json.dumps({"updates": UPDATES, "faults": len(sched["faults"]),
                      "duration": sched["duration_s"]}), flush=True)
    import threading

    stats_path = outdir / "podman-stats.csv"
    stop = threading.Event()

    def _poll():
        with open(stats_path, "w") as fh:
            fh.write("t_s,cpu_pct,mem,net\n")
            t0 = time.time()
            while not stop.is_set():
                try:
                    r = subprocess.run(
                        ["podman", "stats", "--no-stream", "--format",
                         "{{.CPUPerc}},{{.MemUsage}},{{.NetIO}}",
                         "efrs-scale20"],
                        capture_output=True, text=True, timeout=20)
                    fh.write(f"{time.time()-t0:.0f},{r.stdout.strip()}\n")
                    fh.flush()
                except Exception:
                    pass
                stop.wait(5)

    cmd = ["podman", "run", "--rm", "--shm-size=4g", "--name", "efrs-scale20",
           "-v", f"{args.repo_mount}:/ws", "-w", "/ws/efrs-t1",
           "-e", f"ROS_DOMAIN_ID={args.domain}", args.image, "bash", "-lc",
           "source /opt/ros/lyrical/setup.bash && /opt/venv/bin/python "
           "fault_harness/runner.py --schedule experiments/t1_20robot/"
           "sched-scale20.json --out experiments/t1_20robot/rec-scale20.json "
           f"--domain-id {args.domain} --repo /ws/efrs-t1 "
           "--python /opt/venv/bin/python"]
    th = threading.Thread(target=_poll, daemon=True)
    th.start()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        print(r.stdout[-500:] if r.stdout else "")
        print(r.stderr[-500:] if r.stderr else "")
    finally:
        stop.set()
        th.join(timeout=10)
    print("SCALE-DONE")


if __name__ == "__main__":
    main()
