"""Deterministic fault schedules F0-F15 (JSON-serializable builders).

Timing convention (seconds, steady clock; DDS settle handled by runner):
proposes epoch1 @1.5, epoch2 @6.0; fault windows sit in the gaps;
duration 14 s. Wide spacing keeps single instances deterministic under
DDS latency variance; 30-rep structure absorbs residual flakiness.
"""

from __future__ import annotations

ROBOTS3 = ["R1", "R2", "R3"]
DUR = 14.0
P1, P2 = 1.5, 6.0


def base(protocol, faults=(), proposes=None, motion_plan="honest",
         duration=DUR, robots=None):
    return {"protocol": protocol, "robots": list(robots or ROBOTS3),
            "duration_s": duration, "vote_timeout_ms": 1500,
            "proposes": proposes if proposes is not None else [
                {"t": P1, "epoch": 1}, {"t": P2, "epoch": 2}],
            "faults": list(faults), "motion_plan": motion_plan}


def partition(robot, t0, t1):
    return {"t": t0, "kind": "partition", "robot": robot, "until": t1}


def schedules_3robot(protocol):
    F = {}
    F["F0"] = base(protocol)
    F["F1"] = base(protocol, [{"t": 0.5, "kind": "delay",
                               "msg_kind": "commit", "ms": 400}])
    F["F2"] = base(protocol, [{"t": 1.8, "kind": "loss_burst",
                               "msg_kind": "commit", "until": 3.0}])
    F["F3"] = base(protocol, [{"t": 0.5, "kind": "loss_random",
                               "p": 0.3, "seed": 1}])
    F["F4"] = base(protocol, [{"t": 1.0, "kind": "duplicate",
                               "msg_kind": "prepare", "times": 1},
                              {"t": 1.0, "kind": "duplicate",
                               "msg_kind": "commit", "times": 1}])
    F["F5"] = base(protocol, [{"t": 1.0, "kind": "delay",
                               "msg_kind": "prepare", "ms": 2500}])
    F["F6"] = base(protocol, [partition("R3", 0.5, 9.0)])
    F["F7"] = base(protocol, [partition("R3", 2.1, 9.0)])
    F["F8"] = base(protocol, [{"t": 3.0, "kind": "crash_coord",
                               "restart_at": 5.0}])
    F["F9"] = base(protocol, [{"t": 1.7, "kind": "crash_coord",
                               "restart_at": 5.0}],
                     proposes=[{"t": P1, "epoch": 1},
                               {"t": 6.5, "epoch": 1}])
    F["F10"] = base(protocol, [{"t": 1.8, "kind": "crash_robot",
                                "robot": "R3", "restart_at": 7.0}],
                     proposes=[{"t": P1, "epoch": 1},
                               {"t": 8.0, "epoch": 2}])
    F["F11"] = base(protocol, [{"t": 3.0, "kind": "crash_robot",
                                "robot": "R3", "restart_at": 8.0}])
    F["F12"] = base(protocol, [{"t": 1.0, "kind": "delay",
                                "msg_kind": "commit", "epoch": 1,
                                "ms": 8000}])
    F["F13"] = base(protocol, [], motion_plan="stale")
    F["F14"] = base(protocol, [{"t": 2.5, "kind": "sigstop",
                                "robot": "R3", "resume_at": 4.5}])
    F["F15"] = base(protocol, [{"t": 2.5, "kind": "loss_commit_keep_renew",
                                "until": 9.0}])
    return F
