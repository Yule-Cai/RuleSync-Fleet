"""B4 ExactJointOracle: joint branch-and-bound for G4 cross-check.

Independent search paradigm from CAFA-J's prioritized orders (joint
expansion vs decoupled planning): agreement is genuine evidence;
disagreement is a bug or a measured gap (never averaged). Exactness:
joint Dijkstra over (t, joint-state) with incumbent upper bound
(prune prefixes with partial cost strictly above the bound — sound
since totals only grow; equals kept so TIEs are found) + sound BnB
termination (heap-top partial lower-bounds all completions) +
shared CERTIFIED gate + shared cost_of. The incumbent comes from
already-computed feasible costs (baselines AND CAFA — using CAFA's
cost as a bound is sound standard practice: the proof is in the
exhaustive exploration below it, and B4 can still beat it by finding
strictly less). Per-T node guard (frozen): LIMIT beyond.
Prefix-dominance memo caveat predisclosed (memo on full joint state
incl. RD pipeline; no dominance shortcut anywhere). Scope: at most 2
ACTIVE robots (LIMIT otherwise, documented).

Heap entries are 6-tuples (cost, tiebreak, t, node_id, states, None);
node_id is unique per node so comparisons never reach states.
Parent pointers (node_id -> (parent_id, combo)) reconstruct plans
without storing histories in the heap (memory-safe on plateaus).
"""

from __future__ import annotations

import heapq
import itertools
import time

from algorithms.cafa import cost_of, nominal_shortest
from model import tubes as TUB

NODE_GUARD = 200000


def _reconstruct(parents, nid, ids):
    seqs = {rid: [] for rid in ids}
    cur = nid
    chain = []
    while cur != -1 and cur in parents:
        par, cb = parents[cur]
        if cb is not None:
            chain.append(cb)
        cur = par
    chain.reverse()
    for cb in chain:
        for rid, a in zip(ids, cb):
            seqs[rid].append(a)
    return seqs


def _truncate_holds(dyn, active, plan, walls):
    """Drop trailing goal-holding HOLDs per robot (arrival-length plans).

    Physics-preserving by construction: each dropped HOLD is replaced
    by check_certified's identical HOLD-pad, so the certified execution
    is unchanged; only the authored length (what cost_of scores) matches
    the arrival-length representation every other method authors
    (CBS low_level, B0-B3). Without this, B4's joint-length padding
    would systematically overcount holding as interruption.
    Conservative: only HOLD actions with the pre-state already at the
    goal cell are dropped.
    """
    by_id = {r["id"]: r for r in active}
    out = {}
    for rid, seq in plan.items():
        seq = list(seq)
        r = by_id.get(rid)
        if r is None:
            out[rid] = seq
            continue
        goal = tuple(r["goal"])
        while seq and seq[-1] == "HOLD":
            s = (r["start"][0], r["start"][1], r["hd"], r["v"], (),
                 "ADVANCE")
            ok = True
            for a in seq[:-1]:
                s = dyn.step(s, a, walls)
                if s is None:
                    ok = False
                    break
            if not ok:
                break
            if (s[0], s[1]) != goal:
                break
            seq.pop()
        out[rid] = seq
    return out


def b4_oracle(dyn, scenario, incumbent=None):
    t_start = time.monotonic()
    robots = scenario["robots"]
    active = [r for r in robots
              if r["id"] not in set(scenario.get("partitioned", []))]
    if len(active) > 2:
        return {"verdict": "LIMIT", "plan": None, "T": None,
                "cost": None, "limited": True, "proven": False,
                "reason": "B4 scope: >2 active robots",
                "runtime_s": time.monotonic() - t_start}
    walls = frozenset(map(tuple, scenario.get("walls", [])))
    C = scenario["C"]
    D = scenario["D"]
    H = scenario.get("horizon", 14)
    ids = [r["id"] for r in active]
    goals = {r["id"]: tuple(r["goal"]) for r in active}
    part = set(scenario.get("partitioned", []))
    by_id = {r["id"]: r for r in robots}
    s0 = tuple((r["start"][0], r["start"][1], r["hd"], r["v"], (),
                "ADVANCE") for r in active)
    ptubes = {}
    for pid in part:
        r = by_id[pid]
        s0p = (r["start"][0], r["start"][1], r["hd"], r["v"], (),
               "ADVANCE")
        ptubes[pid] = TUB.partitioned_tube(dyn, s0p, H - C, walls)
    _tb = {}

    def tiebreak(states):
        h = 0
        for s, r in zip(states, active):
            g = tuple(r["goal"])
            if (s[0], s[1]) != g:
                key = (s[0], s[1], s[2], s[3], g)
                if key not in _tb:
                    _tb[key] = nominal_shortest(
                        dyn, (s[0], s[1], s[2], s[3]), g, walls)
                d = _tb[key]
                h += d if d is not None else 999
        return h

    def dt_cost(states):
        c = 0
        for s, r in zip(states, active):
            if s[3] == 0 and (s[0], s[1]) != tuple(r["goal"]):
                c += 1
        return c

    best = None
    limited = False
    bound = incumbent if incumbent is not None else None
    ctr = itertools.count()
    parents = {}
    # Strong incumbent bound (sound): completion total >= prefix
    # (downtime + steps) + lat_T - nom_total (BFS lengths sum, latency
    # constant per T). Prune prefixes strictly above best (ties kept).
    # Falls back to downtime-only when any nominal length is unknown.
    nom_total = 0
    nom_ok = True
    for r in active:
        d0 = nominal_shortest(
            dyn, (r["start"][0], r["start"][1], r["hd"], r["v"]),
            tuple(r["goal"]), walls)
        if d0 is None:
            nom_ok = False
            break
        nom_total += d0
    W_L = scenario.get("W_L", 2)
    for T in range(C, D + 1):
        lat_T = W_L * (T - C)
        root = next(ctr)
        parents[root] = (-1, None)
        heap = [(0, tiebreak(s0), C, root, s0, None)]
        seen = {}
        n = 0
        while heap:
            if best is not None and heap and heap[0][0] >= best[2]:
                break
            cost, _, t, nid, states, _ = heapq.heappop(heap)
            n += 1
            if n > NODE_GUARD:
                limited = True
                break
            if bound is not None:
                if nom_ok:
                    if cost + (t - C) > bound - lat_T + nom_total:
                        continue
                elif cost > bound:
                    continue
            key = (t, states)
            if key in seen and seen[key] <= cost:
                continue
            seen[key] = cost
            if all((s[0], s[1]) == goals[rid]
                   for s, rid in zip(states, ids)):
                plan = _reconstruct(parents, nid, ids)
                plan = _truncate_holds(dyn, active, plan, walls)
                for pid in part:
                    plan[pid] = []
                verdict, _ = TUB.check_certified(dyn, scenario, plan,
                                                 T)
                if verdict == "CERTIFIED":
                    c = cost_of(plan, T, scenario, dyn, walls, C)
                    if c is not None and (best is None or c < best[2]):
                        best = (plan, T, c)
                        bound = c if bound is None else min(bound, c)
                continue
            if t >= H:
                continue
            opts = []
            for s in states:
                la = dyn.legal_actions(s, walls)
                opts.append(la if la else ["HOLD"])
            for combo in itertools.product(*opts):
                ns = [dyn.step(s, a, walls) for s, a in zip(states,
                                                            combo)]
                if any(x is None for x in ns):
                    continue
                if t + 1 >= T:
                    hit = False
                    for s in ns:
                        for dx in (-1, 0, 1):
                            for dy in (-1, 0, 1):
                                if TUB.in_forbidden(
                                        (s[0] + dx, s[1] + dy),
                                        scenario["forbidden"]):
                                    hit = True
                    if hit:
                        continue
                fps = [dyn.footprint(s) for s in ns]
                clash = False
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        if fps[i] & fps[j]:
                            clash = True
                if clash:
                    continue
                for cs in dyn.corridor_sets:
                    if sum(1 for f in fps if f & cs) > 1:
                        clash = True
                        break
                if clash:
                    continue
                bad = False
                for f in fps:
                    for _, pt in ptubes.items():
                        if f & pt:
                            bad = True
                            break
                    if bad:
                        break
                if bad:
                    continue
                nid2 = next(ctr)
                parents[nid2] = (nid, combo)
                heapq.heappush(
                    heap, (cost + dt_cost(ns), tiebreak(tuple(ns)),
                           t + 1, nid2, tuple(ns), None))
    runtime = time.monotonic() - t_start
    if best is None:
        if limited:
            return {"verdict": "LIMIT", "plan": None, "T": None,
                    "cost": None, "limited": True, "proven": False,
                    "reason": "B4: node guard, no incumbent",
                    "runtime_s": runtime}
        if D == C:
            return {"verdict": "EMERGENCY_HOLD", "plan": None, "T": None,
                    "cost": None, "limited": False, "proven": False,
                    "reason": "B4: demanded at commit",
                    "runtime_s": runtime}
        return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                "cost": None, "limited": limited, "proven": False,
                "reason": "B4: no certified plan",
                "runtime_s": runtime}
    plan, T, c = best
    if limited:
        if incumbent is not None and c < incumbent:
            v = "BEAT"
        elif incumbent is not None:
            v = "TIE"
        else:
            v = "CERTIFIED"
        return {"verdict": v, "plan": plan, "T": T, "cost": c,
                "reason": "B4 best-found under guard (unproven)",
                "runtime_s": runtime, "limited": True, "proven": False}
    if incumbent is not None and c < incumbent:
        v = "BEAT"
    elif incumbent is not None:
        v = "TIE"
    else:
        v = "CERTIFIED"
    return {"verdict": v, "plan": plan, "T": T, "cost": c,
            "reason": "B4 proven optimal" if v != "BEAT"
            else "B4 strictly improves the incumbent",
            "runtime_s": runtime, "limited": False,
            "proven": v != "BEAT"}
