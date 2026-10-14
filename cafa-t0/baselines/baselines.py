"""CAFA-T0 baselines B0-B3 (frozen definitions).

Shared: cost_of/certificates from algorithms.cafa + model.tubes
(identical accounting and gates for all methods). Result dicts match
CAFA-J shape. Baselines differ ONLY in how (plan, T) is chosen.
B0 GlobalStop, B1 LeaseDrain, B2 IndependentGreedy (FCFS reservations),
B3 TimedConsistentUpdate (timed T + priority-ordered corridors + independent
braking + shared feasibility filter).
"""

from __future__ import annotations

import time

from algorithms.cafa import cost_of, nominal_shortest
from model import tubes as TUB


def _setup(dyn, scenario):
    walls = frozenset(map(tuple, scenario.get("walls", [])))
    C = scenario["C"]
    robots = scenario["robots"]
    part = set(scenario.get("partitioned", []))
    by_id = {r["id"]: r for r in robots}
    s0 = {}
    for r in robots:
        s0[r["id"]] = (r["start"][0], r["start"][1], r["hd"], r["v"],
                       (), "ADVANCE")
    ptubes = {}
    for pid in part:
        r = by_id[pid]
        ptubes[pid] = TUB.partitioned_tube(
            dyn, s0[pid], scenario.get("horizon", 14) - C, walls)
    return walls, C, robots, part, by_id, s0, ptubes


def _blocked_cells_other_robots(states, skip, dyn):
    out = set()
    for rid, s in states.items():
        if rid != skip:
            out |= dyn.footprint(s)
    return out


def _bfs_path(dyn, s0, goal, walls, blocked_extra=frozenset()):
    """BFS shortest ACTION list (position-level) avoiding walls +
    blocked cells. Returns action list or None."""
    from collections import deque
    start = (s0[0], s0[1], s0[2], s0[3])
    dq = deque([(s0, [])])
    seen = {(s0[0], s0[1], s0[2], s0[3], s0[4])}
    while dq:
        s, path = dq.popleft()
        if (s[0], s[1]) == goal:
            return path
        for a in dyn.legal_actions(s, walls):
            ns = dyn.step(s, a, walls)
            fp = dyn.footprint(ns)
            if fp & blocked_extra:
                continue
            key = (ns[0], ns[1], ns[2], ns[3], ns[4])
            if key not in seen:
                seen.add(key)
                dq.append((ns, path + [a]))
    return None


def _rollout_plan(dyn, scenario, paths):
    """Assemble {rid: actions} padded with HOLDs (no T yet)."""
    return {rid: list(p) for rid, p in paths.items()}


def _finish(plan, T, scenario, dyn, walls, C, tag):
    verdict, reason = TUB.check_certified(dyn, scenario, plan, T)
    if verdict != "CERTIFIED":
        return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                "cost": None, "reason": f"{tag}: joint gate: {reason}",
                "runtime_s": 0.0}
    cost = cost_of(plan, T, scenario, dyn, walls, C)
    if cost is None:
        return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                "cost": None, "reason": f"{tag}: unfinished task",
                "runtime_s": 0.0}
    return {"verdict": "CERTIFIED", "plan": plan, "T": T, "cost": cost,
            "reason": f"{tag}: {reason}", "runtime_s": 0.0}


def b0_global_stop(dyn, scenario):
    t0 = time.monotonic()
    walls, C, robots, part, by_id, s0, ptubes = _setup(dyn, scenario)
    H = scenario.get("horizon", 14)
    L = scenario.get("L", 2)
    ids = [r["id"] for r in robots]
    # Phase 1: everybody BRAKEs until stopped.
    states = dict(s0)
    stopped_at = {}
    t = C
    ok = True
    while t <= H:
        allstopped = all(s[3] == 0 for rid, s in states.items()
                         if rid not in part)
        if allstopped:
            break
        nstates = {}
        for rid in ids:
            if rid in part:
                continue
            s = states[rid]
            a = "HOLD" if s[3] == 0 else "BRAKE"
            ns = dyn.step(s, a, walls)
            if ns is None:
                ok = False
                break
            nstates[rid] = ns
            if ns[3] == 0 and rid not in stopped_at:
                stopped_at[rid] = t + 1
        if not ok:
            break
        # Collision check during braking.
        fps = [dyn.footprint(s) for rid, s in nstates.items()]
        for i in range(len(fps)):
            for j in range(i + 1, len(fps)):
                if fps[i] & fps[j]:
                    ok = False
        if not ok:
            break
        states = nstates
        t += 1
    if not ok or any(rid not in stopped_at for rid in ids
                     if rid not in part):
        return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                "cost": None, "reason": "B0: cannot stop fleet",
                "runtime_s": time.monotonic() - t0}
    Tall = max([max(stopped_at.values())] + [C + L])
    # Phase 2: prioritized sequential nominal resume (index order,
    # round-robin; others HOLD where stopped).
    order = [rid for rid in ids if rid not in part]
    cur = dict(states)
    done = {rid: False for rid in order}
    bulk = {rid: [] for rid in ids}
    guard = 0
    while not all(done.values()) and guard < 200:
        guard += 1
        moved = False
        for rid in order:
            if done[rid]:
                continue
            goal = tuple(by_id[rid]["goal"])
            if (cur[rid][0], cur[rid][1]) == goal:
                done[rid] = True
                moved = True
                continue
            blocked = _blocked_cells_other_robots(cur, rid, dyn)
            for _, pt in ptubes.items():
                blocked |= pt
            p = _bfs_path(dyn, cur[rid], goal, walls, blocked)
            if not p:
                bulk[rid].append("HOLD")
                continue
            ns = dyn.step(cur[rid], p[0], walls)
            if ns is None:
                bulk[rid].append("HOLD")
                continue
            # Re-check footprint vs others after move.
            fp = dyn.footprint(ns)
            clash = any(fp & dyn.footprint(cur[o])
                        for o in order if o != rid and not done[o])
            if clash:
                bulk[rid].append("HOLD")
                continue
            cur[rid] = ns
            bulk[rid].append(p[0])
            moved = True
            if (ns[0], ns[1]) == goal:
                done[rid] = True
        if not moved:
            break
    if not all(done.values()):
        return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                "cost": None, "reason": "B0: resume deadlocked",
                "runtime_s": time.monotonic() - t0}
    # Assemble: braking prefix (recomputed verbatim) + resume bulk.
    # (Rebuild deterministically: rerun phase 1 recording actions.)
    plan = {rid: [] for rid in ids}
    states = dict(s0)
    t = C
    while t < Tall:
        for rid in ids:
            if rid in part:
                continue
            s = states[rid]
            a = "HOLD" if s[3] == 0 else "BRAKE"
            plan[rid].append(a)
            states[rid] = dyn.step(s, a, walls)
        t += 1
    # Align bulk lengths then append.
    Lmax = max(len(bulk[rid]) for rid in order) if order else 0
    for rid in order:
        plan[rid] += bulk[rid] + ["HOLD"] * (Lmax - len(bulk[rid]))
    for rid in ids:
        if rid in part:
            plan[rid] = []
    r = _finish(plan, Tall, scenario, dyn, walls, C, "B0")
    r["runtime_s"] = time.monotonic() - t0
    return r


def _nominal_until(dyn, scenario, stop_step):
    """Roll nominal BFS-following motion until stop_step (for B1)."""
    walls, C, robots, part, by_id, s0, ptubes = _setup(dyn, scenario)
    ids = [r["id"] for r in robots]
    states = dict(s0)
    plan = {rid: [] for rid in ids}
    H = scenario.get("horizon", 14)
    for t in range(C, min(stop_step, H)):
        moves = {}
        for rid in ids:
            if rid in part:
                continue
            goal = tuple(by_id[rid]["goal"])
            if (states[rid][0], states[rid][1]) == goal:
                moves[rid] = "HOLD"
                continue
            blocked = _blocked_cells_other_robots(states, rid, dyn)
            for _, pt in ptubes.items():
                blocked |= pt
            p = _bfs_path(dyn, states[rid], goal, walls, blocked)
            moves[rid] = p[0] if p else "HOLD"
        # Stop-before-collision: defer moves that would collide.
        for rid in ids:
            if rid in part or moves[rid] == "HOLD":
                continue
            ns = dyn.step(states[rid], moves[rid], walls)
            if ns is None:
                moves[rid] = "HOLD"
                continue
            fp = dyn.footprint(ns)
            for o in ids:
                if o == rid or o in part:
                    continue
                no = states[o] if moves[o] == "HOLD" else dyn.step(
                    states[o], moves[o], walls)
                if no is not None and fp & dyn.footprint(no):
                    moves[rid] = "HOLD"
                    break
        for rid in ids:
            if rid in part:
                continue
            states[rid] = dyn.step(states[rid], moves[rid], walls)
            plan[rid].append(moves[rid])
    return plan, states


def b1_lease_drain(dyn, scenario):
    t0 = time.monotonic()
    walls, C, robots, part, by_id, s0, ptubes = _setup(dyn, scenario)
    H = scenario.get("horizon", 14)
    L = scenario.get("L", 2)
    ids = [r["id"] for r in robots]
    plan, states = _nominal_until(dyn, scenario, C + L)
    # Brake everybody to stop.
    t = C + len(next(iter(plan.values()))) if plan else C
    guard = 0
    while guard < H:
        guard += 1
        if all(states[rid][3] == 0 for rid in ids if rid not in part):
            break
        for rid in ids:
            if rid in part:
                continue
            a = "HOLD" if states[rid][3] == 0 else "BRAKE"
            ns = dyn.step(states[rid], a, walls)
            if ns is None:
                return {"verdict": "INFEASIBLE", "plan": None,
                        "T": None, "cost": None,
                        "reason": "B1: braking illegal",
                        "runtime_s": time.monotonic() - t0}
            states[rid] = ns
            plan[rid].append(a)
        t += 1
    Tall = t
    # Resume sequential (same as B0 phase 2, from stopped states).
    order = [rid for rid in ids if rid not in part]
    done = {rid: (states[rid][0], states[rid][1]) == tuple(by_id[rid][
        "goal"]) for rid in order}
    bulk = {rid: [] for rid in ids}
    guard = 0
    while not all(done.values()) and guard < 200:
        guard += 1
        moved = False
        for rid in order:
            if done[rid]:
                continue
            goal = tuple(by_id[rid]["goal"])
            if (states[rid][0], states[rid][1]) == goal:
                done[rid] = True
                moved = True
                continue
            blocked = _blocked_cells_other_robots(states, rid, dyn)
            for _, pt in ptubes.items():
                blocked |= pt
            p = _bfs_path(dyn, states[rid], goal, walls, blocked)
            if not p:
                bulk[rid].append("HOLD")
                continue
            ns = dyn.step(states[rid], p[0], walls)
            fp = dyn.footprint(ns)
            if any(fp & dyn.footprint(states[o]) for o in order
                   if o != rid and not done[o]):
                bulk[rid].append("HOLD")
                continue
            states[rid] = ns
            bulk[rid].append(p[0])
            moved = True
            if (ns[0], ns[1]) == goal:
                done[rid] = True
        if not moved:
            break
    if not all(done.values()):
        return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                "cost": None, "reason": "B1: resume deadlocked",
                "runtime_s": time.monotonic() - t0}
    Lmax = max(len(bulk[rid]) for rid in order) if order else 0
    for rid in order:
        plan[rid] += bulk[rid] + ["HOLD"] * (Lmax - len(bulk[rid]))
    r = _finish(plan, Tall, scenario, dyn, walls, C, "B1")
    r["runtime_s"] = time.monotonic() - t0
    return r


def b2_independent_greedy(dyn, scenario):
    t0 = time.monotonic()
    walls, C, robots, part, by_id, s0, ptubes = _setup(dyn, scenario)
    H = scenario.get("horizon", 14)
    D = scenario["D"]
    ids = [r["id"] for r in robots]
    reserved = {}  # (cell, t) -> rid ; corridor (setidx, t) -> rid
    corridor_res = {}
    plan = {}
    Ts = []
    for rid in ids:
        if rid in part:
            plan[rid] = []
            continue
        goal = tuple(by_id[rid]["goal"])
        # Earliest own-certified arrival: BFS avoiding walls, ptubes,
        # others' current cells, and existing reservations.
        static_block = set()
        for o in ids:
            if o != rid:
                static_block |= dyn.footprint(s0[o])
        for _, pt in ptubes.items():
            static_block |= pt
        path = _bfs_path(dyn, s0[rid], goal, walls, static_block)
        if path is None:
            return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                    "cost": None,
                    "reason": f"B2: {rid} no greedy path",
                    "runtime_s": time.monotonic() - t0}
        # Walk the path; HOLD on corridor conflicts (FCFS conservative).
        acts = []
        s = s0[rid]
        t = C
        for a in path:
            while True:
                ns = dyn.step(s, a, walls)
                if ns is None:
                    acts.append("HOLD")
                    t += 1
                    if t > H:
                        break
                    continue
                # Corridor reservation check.
                used = dyn.corridor_use(s, ns)
                clash = any((ci, t) in corridor_res for ci in used)
                # Cell-time reservation check (earlier robots own it).
                fp = dyn.footprint(ns)
                if any((c, t) in reserved for c in fp):
                    clash = True
                if clash:
                    acts.append("HOLD")
                    t += 1
                    if t > H:
                        break
                    continue
                break
            if t > H:
                break
            acts.append(a)
            for c in dyn.footprint(ns):
                reserved[(c, t)] = rid
            for ci in dyn.corridor_use(s, ns):
                corridor_res[(ci, t)] = rid
            s = ns
            t += 1
        plan[rid] = acts
        # Own earliest certified T: own windowed tube (±U over the RD
        # window) around this path avoids forbidden for all t >= T.
        Ti = None
        full = acts + ["HOLD"] * (H - C + 2)
        traj = [s0[rid]]
        sim = s0[rid]
        for kk in range(H - C + 1):
            aa = full[kk] if kk < len(full) else "HOLD"
            sim = dyn.step(sim, aa, walls)
            if sim is None:
                break
            traj.append(sim)
        else:
            for Tcand in range(C, D + 1):
                ok = True
                for k in range(Tcand, H + 1):
                    win = set()
                    for j in range(max(C, k - dyn.RD), k + 1):
                        win |= dyn.footprint(traj[j - C])
                    if any(TUB.in_forbidden(c, scenario["forbidden"])
                           for c in win):
                        ok = False
                        break
                if ok:
                    Ti = Tcand
                    break
        if Ti is None:
            return {"verdict": "INFEASIBLE", "plan": None, "T": None,
                    "cost": None,
                    "reason": f"B2: {rid} never self-certifies",
                    "runtime_s": time.monotonic() - t0}
        Ts.append(Ti)
    Tall = max(Ts) if Ts else C
    r = _finish(plan, Tall, scenario, dyn, walls, C, "B2")
    r["runtime_s"] = time.monotonic() - t0
    return r


def b3_timed_update(dyn, scenario):
    t0 = time.monotonic()
    walls, C, robots, part, by_id, s0, ptubes = _setup(dyn, scenario)
    H = scenario.get("horizon", 14)
    D = scenario["D"]
    ids = [r["id"] for r in robots]
    # Priority order = index order for corridor access.
    for T in range(C, D + 1):
        plan = {}
        feasible = True
        taken = {}  # (corridor idx, t) -> rid
        for rid in ids:
            if rid in part:
                plan[rid] = []
                continue
            goal = tuple(by_id[rid]["goal"])
            blocked = set()
            for _, pt in ptubes.items():
                blocked |= pt
            path = _bfs_path(dyn, s0[rid], goal, walls, blocked)
            if path is None:
                feasible = False
                break
            # Receding brake-to-compliance: take each nominal action
            # only if every BRAKE-to-stop future from the resulting
            # state stays outside forbidden for t >= T; else BRAKE now.
            # Corridor cells held by earlier (priority) robots force HOLD.
            fixed = []
            s = s0[rid]
            t = C
            for a in path:
                # Candidate advance.
                ns = dyn.step(s, a, walls)
                if ns is None:
                    feasible = False
                    break
                used = dyn.corridor_use(s, ns)
                if any((ci, t) in taken for ci in used):
                    ns2 = dyn.step(s, "HOLD", walls)
                    if ns2 is None:
                        feasible = False
                        break
                    fixed.append("HOLD")
                    s = ns2
                    t += 1
                    continue
                # Would advancing now break future compliance at/after T?
                # Check: BRAKE-to-stop tail from ns must avoid forbidden
                # for all steps >= T.
                bs, bt = ns, t + 1
                bad = False
                for _ in range(8):
                    if bt >= T and any(
                            TUB.in_forbidden(c, scenario["forbidden"])
                            for c in dyn.footprint(bs)):
                        bad = True
                        break
                    if bs[3] == 0:
                        break
                    bs = dyn.step(bs, "BRAKE", walls)
                    if bs is None:
                        break
                    bt += 1
                if bad:
                    nsb = dyn.step(s, "BRAKE", walls)
                    if nsb is None:
                        feasible = False
                        break
                    fixed.append("BRAKE")
                    s = nsb
                else:
                    fixed.append(a)
                    s = ns
                    for ci in used:
                        taken[(ci, t)] = rid
                t += 1
                if t > H:
                    break
            if not feasible:
                break
            plan[rid] = fixed
        if not feasible:
            continue
        r = _finish(plan, T, scenario, dyn, walls, C, "B3")
        if r["verdict"] == "CERTIFIED":
            r["runtime_s"] = time.monotonic() - t0
            return r
    return {"verdict": "INFEASIBLE", "plan": None, "T": None,
            "cost": None, "reason": "B3: no timed T certifies",
            "runtime_s": time.monotonic() - t0}
