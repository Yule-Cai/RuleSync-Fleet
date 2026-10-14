"""CAFA-J joint planner + shared search/cost utilities (frozen algorithm).

CAFA-J: outer scan T in C..D (min-COST certified, per report
clarification of the algorithm doc); inner Dijkstra (h=0, exact) over
joint states given T (forbidden active t>=T); shared CERTIFIED gate;
min cost wins. B4 lives in baselines/oracle.py (independent exact
implementation for G4 cross-check).
Cost accounting single-sourced here (cost_of), used by ALL methods.
"""

from __future__ import annotations

import heapq
import itertools

from model import tubes as TUB


def nominal_shortest(dyn, start, goal, walls):
    """BFS shortest action count ignoring other robots (admissible base)."""
    from collections import deque
    s0 = (start[0], start[1], start[2], start[3], (), "ADVANCE")
    seen = {(s0[0], s0[1], s0[2], s0[3], s0[4])}
    dq = deque([(s0, 0)])
    while dq:
        s, d = dq.popleft()
        if (s[0], s[1]) == goal:
            return d
        for a in dyn.legal_actions(s, walls):
            ns = dyn.step(s, a, walls)
            key = (ns[0], ns[1], ns[2], ns[3], ns[4])
            if key not in seen:
                seen.add(key)
                dq.append((ns, d + 1))
    return None


def cost_of(plan, T, scenario, dyn, walls, C, only=None):
    """Frozen cost: downtime + W_L*latency + interruption. plan:
    {rid: [actions]} from C. Unfinished task at H -> INFEASIBLE cost.
    only: restrict scoring to listed robot ids (per-robot accounting
    uses the identical formula; latency counted per call — callers
    comparing across robots must handle the shared term)."""
    robots = scenario["robots"]
    if only is not None:
        robots = [r for r in robots if r["id"] in only]
    H = scenario.get("horizon", 14)
    W_L = scenario.get("W_L", 2)
    W_I = scenario.get("W_I", 1)
    total_dt = 0
    total_int = 0
    for r in robots:
        rid = r["id"]
        s = (r["start"][0], r["start"][1], r["hd"], r["v"], (), "ADVANCE")
        acts = list(plan.get(rid, []))
        nom = nominal_shortest(dyn, (r["start"][0], r["start"][1], r["hd"],
                                     r["v"]), tuple(r["goal"]), walls)
        steps = 0
        reached = None
        t = C
        for a in acts:
            if (s[0], s[1]) == tuple(r["goal"]) and reached is None:
                reached = steps
            if s[3] == 0 and (s[0], s[1]) != tuple(r["goal"]):
                total_dt += 1
            s = dyn.step(s, a, walls)
            if s is None:
                return None
            steps += 1
            t += 1
            if t > H:
                break
        if (s[0], s[1]) == tuple(r["goal"]) and reached is None:
            reached = steps
        if reached is None:
            return None  # task unfinished -> not a complete plan
        total_int += max(0, steps - (nom if nom is not None else 0))
    return total_dt + W_L * (T - C) + W_I * total_int




def cafa_joint(dyn, scenario, seed=0):
    """CAFA-J: prioritized planning over robot orderings (HEURISTIC).

    Exactness disclaimed (see docs §7): joint optima requiring true
    simultaneity (interleaved sharing beyond orderings) can be missed;
    the gap is measured against B4 where computable (G4). For each
    permutation of robots (N! orders): sequential tube-compliant
    low-level optima avoiding earlier robots' full space-time traces;
    joint CERTIFIED gate; min cost wins. Returns dict result with
    'limited' flag (always False here; kept for interface parity).
    seed varies order enumeration (reverse if odd).
    """
    import time
    from algorithms import cbs as CBS
    t_start = time.monotonic()
    walls = frozenset(map(tuple, scenario.get("walls", [])))
    C = scenario["C"]
    D = scenario["D"]
    H = scenario.get("horizon", 14)
    part = set(scenario.get("partitioned", []))
    by_id = {r["id"]: r for r in scenario["robots"]}
    ids = [r["id"] for r in scenario["robots"]]
    part_tubes = {}
    for pid in part:
        r = by_id[pid]
        s0 = (r["start"][0], r["start"][1], r["hd"], r["v"], (),
              "ADVANCE")
        part_tubes[pid] = TUB.partitioned_tube(
            dyn, s0, H - C, walls)
    ptube_cells = set()
    for _, pt in part_tubes.items():
        ptube_cells |= pt
    best = None
    orders = list(itertools.permutations([r for r in ids
                                          if r not in part]))
    if seed % 2 == 1:
        orders = list(reversed(orders))
    # Plus the empty-order baseline is covered (single order suffices
    # when decoupled; all orders tried regardless for uniformity).
    for T in range(C, D + 1):
        for order in orders:
            plans = {}
            cons = {rid: {"cells": set(), "corridor": set()}
                    for rid in ids}
            ok = True
            for rid in order:
                p, _ = CBS.low_level(dyn, scenario, rid, T, walls,
                                     cons[rid], ptube_cells)
                if p is None:
                    ok = False
                    break
                plans[rid] = p
                # Reserve this robot's full windowed trace for later
                # robots in this order.
                r = by_id[rid]
                s = (r["start"][0], r["start"][1], r["hd"], r["v"],
                     (), "ADVANCE")
                traj = [s]
                for k in range(H - C + 1):
                    a = p[k] if k < len(p) else "HOLD"
                    s = dyn.step(s, a, walls)
                    if s is None:
                        break
                    traj.append(s)
                for later in ids:
                    if later == rid or later in part:
                        continue
                    for k in range(C, H + 1):
                        win = set()
                        for j in range(max(C, k - dyn.RD), k + 1):
                            idx = j - C
                            if idx < len(traj):
                                win |= dyn.footprint(traj[idx])
                        for c in win:
                            cons[later]["cells"].add((c, k))
            if not ok:
                continue
            for pid in part:
                plans[pid] = []
            verdict, reason = TUB.check_certified(dyn, scenario, plans,
                                                  T)
            if verdict != "CERTIFIED":
                continue
            cost = cost_of(plans, T, scenario, dyn, walls, C)
            if cost is None:
                continue
            if best is None or cost < best["cost"]:
                best = {"verdict": "CERTIFIED", "plan": plans, "T": T,
                        "cost": cost, "reason": reason}
    runtime = time.monotonic() - t_start
    if best is None:
        # Distinguish emergency-hold demand (D == C) from infeasible.
        if D == C:
            return {"verdict": "EMERGENCY_HOLD", "plan": None, "T": None,
                    "cost": None, "limited": False,
                    "reason": "activation demanded at commit with "
                              "noncompliant states; robots brake to stop, "
                              "deadline violated (counts as G6 failure)",
                    "runtime_s": runtime}
        return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                "cost": None, "limited": False,
                "reason": "no certified (order, T) in [C,D]",
                "runtime_s": runtime}
    best["runtime_s"] = runtime
    best["limited"] = False
    return best
