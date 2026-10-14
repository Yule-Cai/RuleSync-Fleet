"""Shared fault-lifetime semantics (T1.3a workload-semantics correction).

Single source of truth for fault end times, used by the runner (GST +
auto-disarm), the W-HEAL builder, and the tests. ROS-free, pure Python.

fault_end(fault):
  loss_random  -> until if present, else +inf (permanent, W-SUSTAINED)
  partition/partition5 -> until
  crash_robot/crash_coord -> restart_at (or t if absent)
  sigstop -> resume_at (or t)
  delay/duplicate/loss_burst/loss_commit_keep_renew -> until (or t)
  anything else -> t
"""

from __future__ import annotations

import math


def fault_end(f: dict) -> float:
    k = f.get("kind", "")
    if k == "loss_random":
        return float(f["until"]) if "until" in f else math.inf
    if k in ("partition", "partition5"):
        return float(f["until"])
    if k in ("crash_robot", "crash_coord"):
        return float(f.get("restart_at", f.get("t", 0)))
    if k == "sigstop":
        return float(f.get("resume_at", f.get("t", 0)))
    if k in ("delay", "duplicate", "loss_burst", "loss_commit_keep_renew",
             "drop_gen_votes"):
        return float(f.get("until", f.get("t", 0)))
    return float(f.get("t", 0))


def schedule_gst(faults: list) -> float | None:
    """Max fault end; None when no faults carry a finite end."""
    ends = [fault_end(f) for f in faults]
    finite = [e for e in ends if e < math.inf]
    if not ends:
        return None
    if not finite:
        return math.inf  # permanent-only workload (e.g. W-SUSTAINED)
    return max(finite)
