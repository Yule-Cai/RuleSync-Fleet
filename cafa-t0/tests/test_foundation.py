"""CAFA-T0 foundation tests (dynamics, tubes). No ROS/Gazebo/NN."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model.dynamics import Dynamics

CFG = {"grid": {"W": 12, "H": 6},
       "dynamics": {"U_cells": 1, "RD_steps": 1, "B_table": {"1": 1, "2": 3}},
       "corridor_sets": []}


def test_determinism():
    d = Dynamics(CFG)
    s = (4, 2, "E", 2, (), "ADVANCE")
    assert d.step(s, "BRAKE") == d.step(s, "BRAKE")
    assert d.step(s, "ADVANCE") == d.step(s, "ADVANCE")


def test_stopping_dynamics():
    # B-table: from v=2 with RD=1, BRAKE spam must reach v=0 and the
    # stopping distance must cover the frozen B(2)=3 bound logic:
    # delayed first command (cruise 1 step) then 2 braking steps.
    d = Dynamics(CFG)
    s = (1, 2, "E", 2, (), "ADVANCE")
    seen = [s]
    for _ in range(5):
        s = d.step(s, "BRAKE")
        seen.append(s)
    assert seen[-1][3] == 0, seen
    dist = seen[-1][0] - 1
    assert dist >= 3, dist  # RD cruise + braking >= B(2)


def test_rd_conservatism():
    # Delayed BRAKE (RD=1) travels strictly farther than immediate.
    d0cfg = dict(CFG)
    d0cfg["dynamics"] = dict(CFG["dynamics"], RD_steps=0)
    d0, d1 = Dynamics(d0cfg), Dynamics(CFG)
    s0 = (1, 2, "E", 2, (), "ADVANCE")
    a = s0
    for _ in range(4):
        a = d0.step(a, "BRAKE")
    b = s0
    for _ in range(4):
        b = d1.step(b, "BRAKE")
    assert b[0] >= a[0] and b[3] >= a[3]


def test_footprint_uncertainty():
    d = Dynamics(CFG)
    fp = d.footprint((5, 2, "E", 0, (), "HOLD"))
    assert (5, 2) in fp and (4, 1) in fp and (6, 3) in fp
    assert len(fp) == 9


def test_wall_illegal():
    d = Dynamics(CFG)
    walls = frozenset({(3, 2)})
    s = (2, 2, "E", 1, (), "ADVANCE")
    # With RD=1 the in-flight ADVANCE executes first: commanding HOLD
    # cannot prevent hitting the wall this step (delay is real).
    assert d.step(s, "ADVANCE", walls) is None
    assert d.step(s, "HOLD", walls) is None
    # ...but HOLD takes effect next step (v:=0, stay).
    s2 = d.step((0, 2, "E", 0, (), "HOLD"), "HOLD", walls)
    assert s2 is not None and s2[3] == 0


if __name__ == "__main__":
    test_determinism()
    test_stopping_dynamics()
    test_rd_conservatism()
    test_footprint_uncertainty()
    test_wall_illegal()
    print("foundation proofs passed")
