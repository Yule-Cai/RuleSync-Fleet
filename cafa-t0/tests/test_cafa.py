"""CAFA-T0 §12 tests (determinism, certificate basics, accounting)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json

from algorithms.cafa import cafa_joint, cost_of
from baselines.baselines import b3_timed_update
from model import enumerator as ENUM
from model import tubes as TUB
from model.dynamics import Dynamics


def _sc(sid="S1"):
    full = json.load(open(ROOT / "model" / "scenarios.json"))
    sc = dict(full["scenarios"][sid])
    sc["grid"] = full["grid"]
    sc["dynamics"] = full["dynamics"]
    sc["horizon"] = full["horizon"]
    sc["W_L"] = full["objective"]["W_L"]
    sc["W_I"] = full["objective"]["W_I"]
    sc["L"] = full["dynamics"]["L_stale_steps"]
    if "corridor_sets" not in sc:
        sc["corridor_sets"] = []
    dyn = Dynamics({"grid": sc["grid"], "dynamics": sc["dynamics"],
                    "corridor_sets": sc.get("corridor_sets", []),
                    "speed_limit": sc.get("speed_limit")})
    return sc, dyn


def test_determinism():
    sc, dyn = _sc("S1")
    a = cafa_joint(dyn, sc)
    b = cafa_joint(dyn, sc)
    assert a["verdict"] == b["verdict"] and a.get("T") == b.get("T") \
        and a.get("cost") == b.get("cost")


def test_deadline_enforcement():
    # No method may return T > D; S6 must be INFEASIBLE everywhere.
    from baselines.baselines import (b0_global_stop, b1_lease_drain,
                                     b2_independent_greedy)
    from baselines.oracle import b4_oracle
    for fn in (cafa_joint, b0_global_stop, b1_lease_drain,
               b2_independent_greedy, b3_timed_update, b4_oracle):
        sc, dyn = _sc("S6")
        r = fn(dyn, sc)
        assert r["verdict"] in ("INFEASIBLE", "EMERGENCY_HOLD"), \
            (fn.__name__, r["verdict"])
        assert r.get("T") is None or r["T"] <= sc["D"]


def test_s5_immediate_violates():
    # T0: activating S5 at commit time must violate (model expresses
    # the gap) while a later T can certify.
    sc, dyn = _sc("S5")
    trivial = {"R1": [], "R2": []}
    bad = ENUM.verify_certified(sc, trivial, sc["C"])
    assert len(bad) > 0, "S5 immediate activation shows no violation"
    r = cafa_joint(dyn, sc)
    assert r["verdict"] == "CERTIFIED" and r["T"] > sc["C"], r


def test_scenario_wellformedness():
    # Every scenario: starts pairwise disjoint AND one forced ADVANCE
    # step stays disjoint (RD pipeline executes last=ADVANCE first;
    # a first-step collision would deadlock ALL joint plans at t=C).
    full = json.load(open(ROOT / "model" / "scenarios.json"))
    dyn = Dynamics({"grid": full["grid"], "dynamics": full["dynamics"],
                    "corridor_sets": [],
                    "speed_limit": None})
    walls = frozenset()
    for sid, sc in sorted(full["scenarios"].items()):
        ss = [(r["start"][0], r["start"][1], r["hd"], r["v"], (),
               "ADVANCE") for r in sc["robots"]]
        fps0 = [dyn.footprint(s) for s in ss]
        for i in range(len(fps0)):
            for j in range(i + 1, len(fps0)):
                assert not (fps0[i] & fps0[j]), (sid, "start collide")
        ns = [dyn.step(s, "ADVANCE", walls) for s in ss]
        fps1 = [dyn.footprint(s) for s in ns]
        for i in range(len(fps1)):
            for j in range(i + 1, len(fps1)):
                assert not (fps1[i] & fps1[j]), (sid, "step1 collide")


def test_single_cost_source():
    # All methods share cost_of (equal accounting, G-audit).
    import baselines.baselines as B
    import baselines.oracle as O
    import algorithms.cafa as C
    assert B.cost_of is C.cost_of
    assert O.cost_of is C.cost_of


def test_oracle_agrees_trivial():
    # Triangulated G4 smoke: (a) seed agreement, (b) local optimality,
    # (c) B4 verdicts sane (BEAT = fail; LIMIT = scope note).
    from baselines.oracle import b4_oracle
    from run_eval import local_opt_gap
    for sid in ("S5", "S10"):
        sc, dyn = _sc(sid)
        a = cafa_joint(dyn, sc)
        a1 = cafa_joint(dyn, sc, seed=1)
        assert a.get("cost") == a1.get("cost"), (sid, "seed disagree")
        if a.get("verdict") == "CERTIFIED":
            gap = local_opt_gap(dyn, sc, a["plan"], a["T"])
            assert gap is not None and gap >= 0, (sid, "local gap", gap)
        b = b4_oracle(dyn, sc, incumbent=a.get("cost"))
        assert b.get("verdict") != "BEAT", (sid, "B4 beats CAFA", b)
        if b.get("verdict") in ("CERTIFIED", "TIE", "PROVEN"):
            assert a["verdict"] == "CERTIFIED" and \
                a.get("cost") == b.get("cost"), (sid, a, b)


if __name__ == "__main__":
    test_scenario_wellformedness()
    test_determinism()
    test_deadline_enforcement()
    test_s5_immediate_violates()
    test_single_cost_source()
    test_oracle_agrees_trivial()
    print("cafa proofs passed")
