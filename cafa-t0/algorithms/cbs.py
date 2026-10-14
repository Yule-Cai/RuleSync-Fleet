"""CAFA-T0 low-level exact single-robot planner (shared library).

Tube-compliant min-cost single-robot paths under space-time
reservations (Dijkstra over single states; completions in cost order
until one certifies; COMPLETION_CAP guard reports LIMIT). Used by
CAFA-J prioritized order loop. Joint strategy lives in
algorithms/cafa.py; oracle B4 is separately implemented.
"""

from __future__ import annotations

import heapq
import itertools
import time

from algorithms.cafa import cost_of, nominal_shortest
from model import tubes as TUB

COMPLETION_CAP = 500  # low-level completions tried before LIMIT


def single_robot_cert(dyn, scenario, rid, actions, T):
    """Per-robot tube compliance (own uncertainty only): adversarial
    stale branching + suffix, forbidden avoidance post-T, stopped."""
    walls = frozenset(map(tuple, scenario.get("walls", [])))
    C = scenario["C"]
    H = scenario.get("horizon", 14)
    L = scenario.get("L", 2)
    forb = scenario["forbidden"]
    by_id = {r["id"]: r for r in scenario["robots"]}
    r = by_id[rid]
    s0 = (r["start"][0], r["start"][1], r["hd"], r["v"], (), "ADVANCE")
    adv = TUB.adv_tube(dyn, s0, walls, L)
    for t in range(T, H + 1):
        if t <= C + L:
            cells = TUB.tube_cells(dyn, adv)
        else:
            cells = set()
            for s0a in adv:
                sub = TUB.plan_tube(dyn, s0a, actions[L:], t - C - L,
                                    walls)
                if sub is None:
                    return False
                cells |= sub
        if any(TUB.in_forbidden(c, forb) for c in cells):
            return False
    # Stopped by horizon along nominal execution.
    s = s0
    for k in range(H - C + 1):
        a = actions[k] if k < len(actions) else "HOLD"
        s = dyn.step(s, a, walls)
        if s is None:
            return False
    return s[3] == 0


def low_level(dyn, scenario, rid, T, walls, constraints, ptube_cells):
    """Min-cost tube-compliant single-robot path under constraints.
    constraints: set of (cell, t) nominal forbiddens + corridor
    (setidx, t) forbiddens for this robot. Returns (actions, cost) or
    (None, None). Completions enumerated in cost order until one
    certifies (cap COMPLETION_CAP -> (None, None, True) limited)."""
    C = scenario["C"]
    H = scenario.get("horizon", 14)
    by_id = {r["id"]: r for r in scenario["robots"]}
    r = by_id[rid]
    goal = tuple(r["goal"])
    s0 = (r["start"][0], r["start"][1], r["hd"], r["v"], (), "ADVANCE")
    # Dijkstra keyed by (downtime + steps): completions pop in order
    # of total cost (affine shift by the per-(rid,T) constant latency
    # minus nominal length), so the first tube-compliant completion is
    # the minimum-total one. Exact per-robot optimum under constraints.
    import heapq as _hq
    import itertools as _it
    ctr = _it.count()
    from algorithms.cafa import cost_of as _cost
    heap = [(0, next(ctr), C, s0, ())]
    best = {}
    tried = 0
    while heap:
        cost, _, t, s, acts = _hq.heappop(heap)
        key = (t, s)
        if key in best and best[key] <= cost:
            continue
        best[key] = cost
        if (s[0], s[1]) == goal:
            cand = list(acts)
            if single_robot_cert(dyn, scenario, rid, cand, T):
                return cand, _cost({rid: cand}, T, scenario, dyn,
                                   walls, C, only=[rid])
            tried += 1
            if tried >= COMPLETION_CAP:
                return None, None
            continue
        if t >= H:
            continue
        for a in dyn.legal_actions(s, walls) or ("HOLD",):
            ns = dyn.step(s, a, walls)
            if ns is None:
                continue
            if ptube_cells & dyn.footprint(ns):
                continue
            bad = False
            for (cc, tt) in constraints.get("cells", ()):
                if tt == t + 1 and cc in dyn.footprint(ns):
                    bad = True
                    break
            if not bad:
                for (ci, tt) in constraints.get("corridor", ()):
                    if tt == t + 1:
                        bad = True
                        break
            if bad:
                continue
            dc = 1 + (1 if (ns[3] == 0 and (ns[0], ns[1]) != goal)
                      else 0)
            _hq.heappush(heap, (cost + dc, next(ctr), t + 1, ns,
                                tuple(list(acts) + [a])))
    return None, None
