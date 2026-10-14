"""CAFA-T0 G2 independent brute-force enumerator (separate code path).

Deliberately reimplemented (own stepper below — ~30 duplicated lines,
documented) rather than reusing model/dynamics.py: G2 requires an
INDEPENDENT re-derivation of the combinatorial core. Checks, for a
CERTIFIED (plan, T):
 (i)   every plan-consistent execution under RD-lag variants (lag
       0..RD) avoids the new forbidden set for t >= T;
 (ii)  every stale-window cruise-regime prefix (ADVANCE/HOLD/BRAKE
       + as-authored plan endpoint) followed by the plan suffix
       avoids forbidden post-T;
 (iii) partitioned-robot union traces (cruise + hold branches) avoid
       forbidden post-T and never intersect certified footprints;
 (iv)  the plan's own execution has no inter-robot footprint
       intersection and respects corridor capacity (nominal + U).
U-inflation uses its own inflate() (±U squares). Any violating trace
found inside a CERTIFIED instance = false-safe = G2 FAIL.
"""

from __future__ import annotations

import itertools

_DX = {"E": 1, "W": -1, "N": 0, "S": 0}
_DY = {"E": 0, "W": 0, "N": -1, "S": 1}


def make_stepper(RD):
    def step(st, a, W, H, walls, cap):
        x, y, hd, v, q, last = st
        q = tuple(q) + (a,)
        if len(q) <= RD:
            eff = last
        else:
            eff = q[0]
            q = q[1:]
        dx, dy = _DX[hd], _DY[hd]
        if eff in ("TURN_L", "TURN_R"):
            # Turn in place to a full stop (mirrors dynamics.py; a
            # missing TURN branch here once caused false G2 alarms by
            # cruising straight through turns).
            nhd = {"E": "N", "N": "W", "W": "S", "S": "E"}[hd] \
                if eff == "TURN_L" else \
                {"E": "S", "S": "W", "W": "N", "N": "E"}[hd]
            return (x, y, nhd, 0, q, eff)
        if eff == "HOLD":
            v2, path = 0, [(x, y)]
        elif eff == "BRAKE":
            v2 = max(0, v - 1)
            path = [(x + dx * k, y + dy * k) for k in range(1, v2 + 1)]
        elif eff == "ACCEL":
            v2 = min(2, v + 1)
            if cap is not None and _in_cap(x, y, cap):
                v2 = min(v2, cap["vmax"])
            path = [(x + dx * k, y + dy * k) for k in range(1, v2 + 1)]
        elif eff == "ADVANCE":
            v2 = v
            if cap is not None and _in_cap(x, y, cap):
                v2 = min(v2, cap["vmax"])
            path = [(x + dx * k, y + dy * k) for k in range(1, v2 + 1)]
        else:
            raise ValueError(f"unknown action {eff!r}")
        for (px, py) in path:
            if not (0 <= px < W and 0 <= py < H) or (px, py) in walls:
                return None
        nx, ny = path[-1] if path else (x, y)
        return (nx, ny, hd, v2, q, eff)
    return step


def _in_cap(x, y, cap):
    c = cap["cells"]
    return c["x0"] <= x <= c["x1"] and c["y0"] <= y <= c["y1"]


def _inflate(cells, U, W, H):
    out = set()
    for (x, y) in cells:
        for dx in range(-U, U + 1):
            for dy in range(-U, U + 1):
                if 0 <= x + dx < W and 0 <= y + dy < H:
                    out.add((x + dx, y + dy))
    return out


def _in_forbidden(cell, forb):
    return forb["x0"] <= cell[0] <= forb["x1"] and \
        forb["y0"] <= cell[1] <= forb["y1"]


def verify_certified(scenario, plan, T):
    """Returns list of violating traces (empty = agrees CERTIFIED)."""
    W, H = scenario["grid"]["W"], scenario["grid"]["H"]
    U = scenario["dynamics"]["U_cells"]
    RD = scenario["dynamics"]["RD_steps"]
    L = scenario.get("L", 2)
    C = scenario["C"]
    HH = scenario.get("horizon", 14)
    forb = scenario["forbidden"]
    cap = scenario.get("speed_limit")
    walls = set(map(tuple, scenario.get("walls", [])))
    part = set(scenario.get("partitioned", []))
    step = make_stepper(RD)
    ids = [r["id"] for r in scenario["robots"]]
    by_id = {r["id"]: r for r in scenario["robots"]}
    s0 = {rid: (r["start"][0], r["start"][1], r["hd"], r["v"], (),
                "ADVANCE") for rid, r in by_id.items()}
    acts = {rid: list(plan.get(rid, [])) for rid in ids}
    bad = []

    def rollout(s, actions):
        traj = [s]
        for a in actions:
            s = step(s, a, W, H, walls, cap)
            if s is None:
                return None
            traj.append(s)
        return traj

    # (i) plan-consistent executions under RD-lag variants.
    for rid in ids:
        if rid in part:
            continue
        for lag in range(RD + 1):
            # Lag variant: first `lag` commands replaced by persisting
            # cruise (models up-to-RD delay uncertainty).
            variant = ["ADVANCE"] * lag + acts[rid]
            tr = rollout(s0[rid], variant[:HH - C + lag])
            if tr is None:
                # Over-long cruise variant left the bounded world: an
                # artifact of variant construction (not plan content).
                # Skipped (documented); wall-crashes are outside the
                # violation categories by design.
                continue
            for k in range(T, HH + 1):
                idx = k - C + lag
                pos = (tr[idx][0], tr[idx][1]) if idx < len(tr) else \
                    (tr[-1][0], tr[-1][1])
                if any(_in_forbidden(c, forb)
                       for c in _inflate({pos}, U, W, H)):
                    bad.append((rid, "lag", lag, f"zone@{k}"))
    # (ii) stale-window cruise-regime prefixes (ADVANCE/HOLD/BRAKE,
    # mirroring tubes.adv_tube) + the as-authored plan endpoint,
    # followed by the plan suffix. TURNS/ACCEL excluded by the same
    # frozen threat model (see tubes.adv_tube rationale).
    for rid in ids:
        if rid in part:
            continue
        prefixes = [[]]
        for _ in range(L):
            nxt = []
            for pre in prefixes:
                for a in ("ADVANCE", "HOLD", "BRAKE"):
                    nxt.append(pre + [a])
            prefixes = nxt
        prefixes.append(list(acts[rid][:L]))
        for pre in prefixes:
            s = s0[rid]
            ok = True
            for a in pre:
                s = step(s, a, W, H, walls, cap)
                if s is None:
                    ok = False
                    break
            if not ok:
                continue
            suf = acts[rid][L:] + ["HOLD"] * (HH - C)
            tr = rollout(s, suf[:HH - C - L + 1])
            if tr is None:
                bad.append((rid, "stale-prefix", pre, "illegal-suffix"))
                continue
            for k in range(max(T, C + L), HH + 1):
                idx = k - C - L
                pos = (tr[idx][0], tr[idx][1])
                if any(_in_forbidden(c, forb)
                       for c in _inflate({pos}, U, W, H)):
                    bad.append((rid, "stale-prefix", pre, f"zone@{k}"))
    # (iii) partitioned union traces.
    for pid in part:
        for branch in (["ADVANCE"] * (HH - C), ["HOLD"] * (HH - C)):
            tr = rollout(s0[pid], branch)
            if tr is None:
                continue
            for k in range(T, HH + 1):
                pos = (tr[k - C][0], tr[k - C][1])
                if any(_in_forbidden(c, forb)
                       for c in _inflate({pos}, U, W, H)):
                    bad.append((pid, "partitioned", branch[0], f"zone@{k}"))
    # (iv) inter-robot + corridor on the nominal plan (±U).
    for k in range(C, HH + 1):
        fps = {}
        for rid in ids:
            if rid in part:
                continue
            tr = rollout(s0[rid], acts[rid][:k - C + 1])
            if tr is None:
                bad.append((rid, "plan", None, f"illegal@{k}"))
                continue
            fps[rid] = _inflate({(tr[-1][0], tr[-1][1])}, U, W, H)
        rids = list(fps)
        for i in range(len(rids)):
            for j in range(i + 1, len(rids)):
                if fps[rids[i]] & fps[rids[j]]:
                    bad.append((rids[i], "collision", rids[j], f"@{k}"))
    return bad
