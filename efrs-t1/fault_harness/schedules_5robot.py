"""5-robot systematic schedules + I2 integrity schedule (builders).

Topologies (coordinator = C): 4+1, 3+2, coordinator-isolated, two
independent isolates. Combined schedules per brief. 20 reps each
(driven by rep.py --robots override... see scale_20robot handles its
own loop). I2: same-epoch different-hash + mutated payload with stale
hash; EFRS must reject + hold/reconcile.
"""

from __future__ import annotations

ROBOTS5 = ["R1", "R2", "R3", "R4", "R5"]
DUR = 16.0


def base(protocol, faults=(), proposes=None, robots=None, duration=DUR,
         motion_plan="honest"):
    return {"protocol": protocol, "robots": list(robots or ROBOTS5),
            "duration_s": duration, "vote_timeout_ms": 1500,
            "proposes": proposes if proposes is not None else [
                {"t": 1.5, "epoch": 1}, {"t": 6.0, "epoch": 2}],
            "faults": list(faults), "motion_plan": motion_plan}


def part5(isolates, t0, t1):
    """Partition spec; isolates = list of robot names and/or name lists.

    Each entry becomes one isolate group; the runner blocks every
    isolate's fault-plane traffic (star protocol: equivalent to full
    isolation from the coordinator side). Topology labels persist in
    the schedule record for the report.
    """
    groups = [list(g) if isinstance(g, list) else [g] for g in isolates]
    return {"t": t0, "kind": "partition5", "groups": groups, "until": t1}


def schedules_5robot(protocol):
    S = {}
    S["P41"] = base(protocol, [part5(["R5"], 0.5, 10.0)])
    S["P32"] = base(protocol, [part5([["R4", "R5"]], 0.5, 10.0)])
    S["PCOORD"] = base(protocol, [part5(
        [["R1", "R2", "R3", "R4", "R5"]], 0.5, 10.0)])
    S["P2ISO"] = base(protocol, [part5(["R2", "R4"], 0.5, 10.0)])
    S["C_PLUS_LATE"] = base(protocol, [part5(["R5"], 0.5, 10.0),
                                       {"t": 1.0, "kind": "delay",
                                        "msg_kind": "commit", "epoch": 1,
                                        "ms": 8000}])
    S["C_PART_RESTART"] = base(protocol, [part5(["R5"], 0.5, 10.0),
                                          {"t": 3.0, "kind": "crash_robot",
                                           "robot": "R4",
                                           "restart_at": 9.0}])
    S["C_COORD_ROBOT"] = base(protocol, [
        {"t": 3.0, "kind": "crash_coord", "restart_at": 6.0},
        {"t": 8.0, "kind": "crash_robot", "robot": "R2",
         "restart_at": 12.0}])
    S["C_LOSS_REORDER"] = base(protocol, [
        {"t": 0.5, "kind": "loss_random", "p": 0.3, "seed": 3},
        {"t": 1.0, "kind": "delay", "msg_kind": "prepare", "ms": 900}])
    S["C_STALE_RECONNECT"] = base(
        protocol, [part5(["R1"], 0.5, 7.0)], motion_plan="stale")
    return S


def schedule_i2(protocol):
    """I2 content-integrity: same epoch different hash + mutated payload
    with stale hash. EFRS must reject + hold/reconcile."""
    return base(protocol, [
        {"t": 1.0, "kind": "mutate", "fid": "i2a", "node": "coordinator",
         "msg_kind": "commit", "set": {"hash": "hX-of-evil"}},
    ], proposes=[{"t": 1.5, "epoch": 1}])
