"""W-HEAL construction (frozen BEFORE execution; T1.2 §H2).

Builds SCALE20_EVENTUAL_HEAL_LIVENESS from the frozen T1 scale fault
sequence: keeps transient fault ORDERING; every unterminated
loss_random gets until = t + 3000 ms (frozen: exactly two 1500 ms
prepare windows); all other finite faults keep frozen durations.
Sequential logical issue (epochs 1..100, §I); duration cap 600 s.
GST = end of the last fault; verified below (no fault at/after GST
except none; proposes continue past GST by construction).

Usage: python3 build_wheal.py  (writes sched-wheal.json + prints GST)
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path("/home/gamer/RuleSync-Fleet/efrs-t1/experiments/t1_20robot/"
           "sched-scale20.json")
OUT = Path("/home/gamer/RuleSync-Fleet/efrs-t12/experiments/t12_scale/"
           "sched-wheal.json")
LOSS_LIFETIME_MS = 3000
DURATION_S = 600.0
N_UPDATES = 100


def fault_end(f) -> float:
    k = f["kind"]
    if k == "loss_random":
        return float(f["t"]) + LOSS_LIFETIME_MS / 1000.0
    if k in ("partition", "partition5"):
        return float(f["until"])
    if k in ("crash_robot", "crash_coord"):
        return float(f.get("restart_at", f["t"]))
    if k == "sigstop":
        return float(f.get("resume_at", f["t"]))
    if k in ("delay", "duplicate", "loss_burst"):
        return float(f.get("until", f.get("t", 0)))
    return float(f.get("t", 0))


def main() -> None:
    src = json.loads(Path(SRC).read_text())
    faults = []
    for f in src["faults"]:
        f = dict(f)
        if f["kind"] == "loss_random" and "until" not in f:
            f["until"] = float(f["t"]) + LOSS_LIFETIME_MS / 1000.0
        faults.append(f)
    gst = max(fault_end(f) for f in faults)
    assert all("until" in f or f["kind"] not in ("loss_random",)
               for f in faults), "unterminated loss remains"
    assert gst < DURATION_S
    sched = {"duration_s": DURATION_S,
             "faults": faults,
             "motion_plan": src.get("motion_plan", "honest"),
             "protocol": "efrs",
             "propose_mode": "sequential",
             "n_updates": N_UPDATES,
             "robots": src["robots"],
             "vote_timeout_ms": src.get("vote_timeout_ms", 1500),
             "w_heal": {"loss_lifetime_ms": LOSS_LIFETIME_MS,
                        "gst": gst,
                        "derived_from": "efrs-t1 sched-scale20.json"}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sched, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"wrote": str(OUT), "n_faults": len(faults),
                      "gst": gst, "duration_s": DURATION_S,
                      "n_updates": N_UPDATES}, sort_keys=True))


if __name__ == "__main__":
    main()
