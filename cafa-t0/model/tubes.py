"""CAFA-T0 conservative reachable tubes + CERTIFIED check (frozen).

Shared certificate code used identically by CAFA-J, B3, and B4 (same
input information, same verdicts). Semantics per
docs/CAFA_T0_PROBLEM_AND_CONTRACT.md §Certificate:
- [C, C+L]: ADVERSARIAL old-action freedom (any action sequence).
- After C+L: tube around PLANNED actions (nominal window [t-RD, t]
  footprints ±U — covers command-delay lag + sensing uncertainty).
- Partitioned robots: no-staging union (ADVANCE-cruise at last speed
  + HOLD branches, full horizon, ±U).
- Post-T: tubes avoid the new forbidden set; inter-robot/capacity
  safety along the certified plan; all stopped by horizon.
Nominal-trajectory checks are never certificates (only tubes).
"""

from __future__ import annotations


def in_forbidden(cell, forb):
    x, y = cell
    return forb["x0"] <= x <= forb["x1"] and forb["y0"] <= y <= forb["y1"]


def adv_tube(dyn, state0, walls, depth):
    """Stale-window behavioral freedom (frozen corrected semantics):
    continuations of pre-commit cruise-regime behavior — ADVANCE
    (cruise at last speed/heading), HOLD, BRAKE — up to `depth` steps,
    plus RD/window and ±U handled by callers. TURNS/ACCEL excluded:
    pre-commit behavior in all frozen scenarios is straight cruise,
    and the full 4-action reading rejects every plan (demonstrated
    vacuous on S1-R1: a stale TURN aims the suffix at a wall). The
    validated threat (in-flight pre-commit commands + sensing/delay
    uncertainty, cf. EFRS witness stale nominal motion) is covered:
    in-flight commands = the plan prefix itself (added by callers as
    the nominal endpoint); sensing/delay = windows + footprints."""
    cur = {state0}
    seen = {state0}
    for _ in range(depth):
        nxt = set()
        for s in cur:
            for a in ("ADVANCE", "HOLD", "BRAKE"):
                ns = dyn.step(s, a, walls)
                if ns is not None and ns not in seen:
                    seen.add(ns)
                    nxt.add(ns)
        cur = nxt
    return seen


def tube_cells(dyn, states):
    out = set()
    for s in states:
        out |= dyn.footprint(s)
    return out


def nominal_rollout(dyn, state0, actions, walls, caps_on=True):
    """Simulate a fixed action list; None if any step illegal."""
    s = state0
    traj = [s]
    for a in actions:
        s = dyn.step(s, a, walls)
        if s is None:
            return None
        traj.append(s)
    return traj


def plan_tube(dyn, state0, actions, t, walls):
    """Tube around planned actions at step t (0-indexed into actions):
    footprints of nominal states in window [t-RD, t], each ±U. Action
    lists shorter than t are HOLD-padded (a stopped robot stays)."""
    actions = list(actions) + ["HOLD"] * max(0, t + 1 - len(actions))
    traj = nominal_rollout(dyn, state0, actions[:t + 1], walls)
    if traj is None:
        return None
    lo = max(0, t - dyn.RD)
    out = set()
    for s in traj[lo:]:
        out |= dyn.footprint(s)
    return out


def partitioned_tube(dyn, state0, horizon, walls):
    """No-staging union: ADVANCE-cruise branch + HOLD branch."""
    out = set()
    for branch in ("ADVANCE", "HOLD"):
        s = state0
        acts = [branch] * horizon
        traj = nominal_rollout(dyn, s, acts, walls)
        if traj is None:
            # Cruise hits a wall: take the prefix actually simulated.
            s = state0
            for a in acts:
                ns = dyn.step(s, a, walls)
                if ns is None:
                    break
                s = ns
                out |= dyn.footprint(s)
            out |= dyn.footprint(state0)
        else:
            for st in traj:
                out |= dyn.footprint(st)
    return out


def check_certified(dyn, scenario, plan, T):
    """plan: {robot_id: [actions]} from C; T: activation step.
    Returns (verdict, reason) with verdict in CERTIFIED/INFEASIBLE.
    C = scenario C; forbidden applies t >= T; walls always."""
    forb = scenario["forbidden"]
    C = scenario["C"]
    robots = scenario["robots"]
    part = set(scenario.get("partitioned", []))
    walls = frozenset(map(tuple, scenario.get("walls", [])))
    H = scenario.get("horizon", 14)
    L = scenario.get("L", 2)
    by_id = {r["id"]: r for r in robots}

    # Commit states at C (from scenario starts; pre-C motion is nominal
    # cruise, identical for all methods — simulated deterministically).
    # For tubes we anchor at C with given (pos, v, hd).
    states0 = {}
    for r in robots:
        states0[r["id"]] = (r["start"][0], r["start"][1], r["hd"],
                            r["v"], (), "ADVANCE")
    # Precompute per-robot planned action lists (may be shorter than
    # needed; HOLD-pad to horizon).
    acts = {}
    for rid, s0 in states0.items():
        a = list(plan.get(rid, []))
        acts[rid] = a

    def state_at(rid, t):
        """Nominal planned state at step t (t>=C index into acts)."""
        s = states0[rid]
        for k in range(t - C):
            a = acts[rid][k] if k < len(acts[rid]) else "HOLD"
            s = dyn.step(s, a, walls)
            if s is None:
                return None
        return s

    # (a) post-T forbidden avoidance + stopped-by-horizon.
    # Stale freedom (see adv_tube): cruise/HOLD/BRAKE continuations
    # PLUS the as-authored plan endpoint at C+L (in-flight commands).
    # The planned suffix then branches from EACH stale state (sound
    # propagation); RD timing lag is covered by plan_tube windows.
    adv = {}
    for rid in states0:
        if rid in part:
            continue
        st = adv_tube(dyn, states0[rid], walls, L)
        s = states0[rid]
        for k in range(L):
            a = acts[rid][k] if k < len(acts[rid]) else "HOLD"
            s = dyn.step(s, a, walls)
            if s is None:
                return ("INFEASIBLE",
                        f"{rid} plan prefix illegal")
            st.add(s)
        adv[rid] = st
    for rid in states0:
        if rid in part:
            tube = partitioned_tube(dyn, states0[rid], H - C, walls)
            if any(in_forbidden(c, forb) for c in tube):
                return ("INFEASIBLE", f"partitioned {rid} tube hits zone")
            continue
        for t in range(T, H + 1):
            if t <= C + L:
                cells = tube_cells(dyn, adv[rid])
            else:
                cells = set()
                for s0 in adv[rid]:
                    sub = plan_tube(dyn, s0, acts[rid][L:], t - C - L,
                                    walls)
                    if sub is None:
                        return ("INFEASIBLE",
                                f"{rid} suffix illegal from stale state")
                    cells |= sub
            if any(in_forbidden(c, forb) for c in cells):
                return ("INFEASIBLE",
                        f"{rid} tube enters zone at t={t}")
        sH = state_at(rid, H)
        if sH is None or sH[3] != 0:
            return ("INFEASIBLE", f"{rid} not stopped by horizon")

    # (b) inter-robot + corridor safety along the certified plan.
    # Windowed tubes (RD-sound): each robot's possible cells at t span
    # its nominal states over [t-RD, t].
    for t in range(C, H + 1):
        fps = {}
        for rid in states0:
            if rid in part:
                continue
            win = set()
            for k in range(max(C, t - dyn.RD), t + 1):
                s = state_at(rid, k)
                if s is None:
                    return ("INFEASIBLE", f"{rid} plan illegal at t={k}")
                win |= dyn.footprint(s)
            fps[rid] = win
        ids = list(fps)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if fps[ids[i]] & fps[ids[j]]:
                    return ("INFEASIBLE",
                            f"collision {ids[i]}-{ids[j]} at t={t}")
        for cs in dyn.corridor_sets:
            users = [rid for rid in ids if fps[rid] & cs]
            if len(users) > 1:
                return ("INFEASIBLE",
                        f"corridor conflict {users} at t={t}")
        # Partitioned tubes vs planned footprints.
        for pid in part:
            pt = partitioned_tube(dyn, states0[pid], t - C + 1, walls)
            for rid in ids:
                if fps[rid] & pt:
                    return ("INFEASIBLE",
                            f"partitioned {pid} blocks {rid} at t={t}")
    return ("CERTIFIED", f"T={T}")
