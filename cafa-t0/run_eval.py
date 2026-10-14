"""CAFA-T0 frozen evaluation (run EXACTLY as frozen, no tuning).

Every method (CAFA-J, B0-B4) on every scenario (S1-S10). Plus:
- T0 probe: force activation at T=C on S5 through the enumerator;
  a violation MUST appear (else the model cannot express the gap).
- S10 tripwire: CAFA cost must EQUAL B3 cost (else accounting bug).
- G2: independent enumerator over every CERTIFIED instance; any
  violating trace = false-safe = FAIL.
Writes reports/cafa_t0_results.json + prints gate table.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT))

from algorithms.cafa import cafa_joint
from baselines.baselines import (b0_global_stop, b1_lease_drain,
                                 b2_independent_greedy, b3_timed_update)
from baselines.oracle import b4_oracle
from model import enumerator as ENUM
from model.dynamics import Dynamics

METHODS = {
    "CAFA-J": cafa_joint,
    "B0": b0_global_stop,
    "B1": b1_lease_drain,
    "B2": b2_independent_greedy,
    "B3": b3_timed_update,
}


def run_b4(dyn, sc, incumbent):
    from baselines.oracle import b4_oracle
    t0 = time.monotonic()
    try:
        r = b4_oracle(dyn, sc, incumbent=incumbent)
    except Exception as e:
        r = {"verdict": "CRASH", "plan": None, "T": None, "cost": None,
             "reason": f"{type(e).__name__}: {e}"[:200]}
    r = dict(r)
    r["wall_s"] = round(time.monotonic() - t0, 3)
    return r


def load_scenarios():
    return json.load(open(ROOT / "model" / "scenarios.json"))


def run_one(method, sid, sc_full):
    sc, dyn = _sc_dyn(sid, sc_full)
    t0 = time.monotonic()
    try:
        r = METHODS[method](dyn, sc)
    except Exception as e:  # never silently pass; record crash
        r = {"verdict": "CRASH", "plan": None, "T": None, "cost": None,
             "reason": f"{type(e).__name__}: {e}"[:200]}
    wall = time.monotonic() - t0
    r = dict(r)
    r["wall_s"] = round(wall, 3)
    # G2: enumerator over CERTIFIED instances (independent path).
    r["false_safe_traces"] = []
    if r.get("verdict") == "CERTIFIED" and r.get("plan") is not None:
        esc = dict(sc)
        esc["dynamics"] = dict(sc["dynamics"])
        bad = ENUM.verify_certified(esc, r["plan"], r["T"])
        r["false_safe_traces"] = bad[:8]
    return r


def _sc_dyn(sid, sc_full):
    from model.dynamics import Dynamics
    sc = dict(sc_full["scenarios"][sid])
    sc["grid"] = sc_full["grid"]
    sc["dynamics"] = sc_full["dynamics"]
    sc["horizon"] = sc_full["horizon"]
    sc["W_L"] = sc_full["objective"]["W_L"]
    sc["W_I"] = sc_full["objective"]["W_I"]
    sc["L"] = sc_full["dynamics"]["L_stale_steps"]
    if "corridor_sets" not in sc:
        sc["corridor_sets"] = []
    dyn = Dynamics({"grid": sc["grid"], "dynamics": sc["dynamics"],
                    "corridor_sets": sc.get("corridor_sets", []),
                    "speed_limit": sc.get("speed_limit")})
    return sc, dyn


def local_opt_gap(dyn, sc, plan, T):
    """G4b: min over single-robot deviations (exact low-level replan
    holding others' windowed traces fixed) of (dev_cost - plan_cost).
    Negative = CAFA improvable (gap found). None if plan missing."""
    from algorithms import cbs as CBS
    from algorithms.cafa import cost_of
    if plan is None:
        return None
    walls = frozenset(map(tuple, sc.get("walls", [])))
    C = sc["C"]
    H = sc.get("horizon", 14)
    by_id = {r["id"]: r for r in sc["robots"]}
    ids = [r["id"] for r in sc["robots"]]
    part = set(sc.get("partitioned", []))
    ptube_cells = set()
    for pid in part:
        r = by_id[pid]
        s0 = (r["start"][0], r["start"][1], r["hd"], r["v"], (),
              "ADVANCE")
        from model import tubes as TUB
        ptube_cells |= TUB.partitioned_tube(dyn, s0, H - C, walls)
    base = cost_of(plan, T, sc, dyn, walls, C)
    if base is None:
        return None
    best = 0
    # Others' windowed traces as constraints for the deviating robot.
    for rid in ids:
        if rid in part:
            continue
        cons = {"cells": set(), "corridor": set()}
        for o in ids:
            if o == rid or o in part:
                continue
            r = by_id[o]
            s = (r["start"][0], r["start"][1], r["hd"], r["v"], (),
                 "ADVANCE")
            traj = [s]
            acts = plan.get(o, [])
            for k in range(H - C + 1):
                a = acts[k] if k < len(acts) else "HOLD"
                s = dyn.step(s, a, walls)
                if s is None:
                    break
                traj.append(s)
            for k in range(C, H + 1):
                win = set()
                for j in range(max(C, k - dyn.RD), k + 1):
                    idx = j - C
                    if idx < len(traj):
                        win |= dyn.footprint(traj[idx])
                for c in win:
                    cons["cells"].add((c, k))
        p, _ = CBS.low_level(dyn, sc, rid, T, walls, cons,
                             ptube_cells)
        if p is None:
            continue
        nplan = dict(plan)
        nplan[rid] = p
        from model import tubes as TUB2
        v, _ = TUB2.check_certified(dyn, sc, nplan, T)
        if v != "CERTIFIED":
            continue
        c = cost_of(nplan, T, sc, dyn, walls, C)
        if c is not None and c < base + best:
            best = c - base
    return best


def main():
    sc_full = load_scenarios()
    out = {"methods": list(METHODS) + ["B4"], "scenarios": {}}
    for sid in ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9",
                "S10"]:
        out["scenarios"][sid] = {}
        for m in METHODS:
            r = run_one(m, sid, sc_full)
            slim = {"verdict": r["verdict"], "T": r.get("T"),
                    "cost": r.get("cost"), "reason": r.get("reason"),
                    "wall_s": r.get("wall_s"),
                    "false_safe": len(r.get("false_safe_traces", []))}
            if r.get("verdict") == "CERTIFIED":
                slim["plan"] = r["plan"]
            out["scenarios"][sid][m] = slim
            print(f"{sid} {m}: {slim['verdict']} T={slim['T']} "
                  f"cost={slim['cost']} fs={slim['false_safe']} "
                  f"({slim['wall_s']}s)", flush=True)
        # B4 with incumbent = min feasible cost found (CAFA + baselines).
        feas = [out["scenarios"][sid][m]["cost"]
                for m in METHODS
                if out["scenarios"][sid][m]["verdict"] == "CERTIFIED"
                and out["scenarios"][sid][m]["cost"] is not None]
        inc = min(feas) if feas else None
        sc, dyn = _sc_dyn(sid, sc_full)
        rb = run_b4(dyn, sc, inc)
        # G4a seed agreement + G4b local optimality for CAFA plans.
        from algorithms.cafa import cafa_joint as _cj
        r1 = _cj(dyn, sc, seed=1)
        g4a = (r1.get("cost") == out["scenarios"][sid]["CAFA-J"].get(
            "cost"))
        gap = None
        cj = out["scenarios"][sid]["CAFA-J"]
        if cj.get("verdict") == "CERTIFIED" and cj.get("plan"):
            gap = local_opt_gap(dyn, sc, cj["plan"], cj["T"])
        slim = {"verdict": rb["verdict"], "T": rb.get("T"),
                "cost": rb.get("cost"), "reason": rb.get("reason"),
                "wall_s": rb.get("wall_s"),
                "limited": rb.get("limited", False),
                "proven": rb.get("proven", False),
                "seed_agree": g4a,
                "local_gap": gap}
        out["scenarios"][sid]["B4"] = slim
        print(f"{sid} B4: {slim['verdict']} T={slim['T']} "
              f"cost={slim['cost']} lim={slim['limited']} "
              f"seed_agree={g4a} local_gap={gap} "
              f"({slim['wall_s']}s)", flush=True)
    # T0 probe: force T=C on S5 -> violation must appear.
    sc5 = dict(sc_full["scenarios"]["S5"])
    for k in ("grid", "dynamics", "horizon"):
        sc5[k] = sc_full[k] if k != "dynamics" else sc_full[k]
    sc5["W_L"] = 2
    sc5["W_I"] = 1
    sc5["L"] = 2
    dyn5 = Dynamics({"grid": sc5["grid"], "dynamics": sc5["dynamics"],
                     "corridor_sets": []})
    trivial = {rid: [] for rid in ("R1", "R2")}
    bad = ENUM.verify_certified(sc5, trivial, sc5["C"])
    out["T0_probe_violation_found"] = len(bad) > 0
    print("T0 probe (S5 immediate activation violates):",
          out["T0_probe_violation_found"])
    # S10 tripwire.
    s10 = out["scenarios"]["S10"]
    out["S10_tripwire_equal"] = (
        s10["CAFA-J"]["verdict"] == s10["B3"]["verdict"] == "CERTIFIED"
        and s10["CAFA-J"]["cost"] == s10["B3"]["cost"])
    print("S10 tripwire (CAFA==B3):", out["S10_tripwire_equal"],
          s10["CAFA-J"].get("cost"), s10["B3"].get("cost"))
    (ROOT / "reports" / "cafa_t0_results.json").write_text(
        json.dumps(out, indent=1, sort_keys=True))
    print("wrote reports/cafa_t0_results.json")


if __name__ == "__main__":
    main()
