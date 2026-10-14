"""CAFA-T0 finite discrete dynamics (frozen contract implementation).

Grid W×H; robots (x, y, heading, v), v in {0,1,2}. Actions HOLD /
ADVANCE / BRAKE / ACCEL per docs/CAFA_T0_PROBLEM_AND_CONTRACT.md.
Uncertainty U (position interval), RD (control delay steps), corridor
capacity sets, braking table B. Deterministic; no randomness.
"""

from __future__ import annotations

import functools

ACTIONS = ("HOLD", "ADVANCE", "BRAKE", "ACCEL", "TURN_L", "TURN_R")
HEADINGS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
_LEFT = {"E": "N", "N": "W", "W": "S", "S": "E"}
_RIGHT = {"E": "S", "S": "W", "W": "N", "N": "E"}


class Dynamics:
    def __init__(self, cfg):
        self.W = cfg["grid"]["W"]
        self.H = cfg["grid"]["H"]
        self.U = cfg["dynamics"]["U_cells"]
        self.RD = cfg["dynamics"]["RD_steps"]
        self.B = {int(k): v for k, v in cfg["dynamics"]["B_table"].items()}
        self.corridor_sets = [set(map(tuple, s))
                              for s in cfg.get("corridor_sets", [])]
        self.speed_limit = cfg.get("speed_limit", None)

    def in_bounds(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H

    def cell_blocked_static(self, x, y, walls):
        return (not self.in_bounds(x, y)) or ((x, y) in walls)

    def step(self, state, action, walls=frozenset()):
        """One robot step. state=(x,y,hd,v,queue,last). RD semantics:
        a command takes effect RD steps after issue; meanwhile the
        previous effective action persists (pipeline starts full of
        ADVANCE cruise at the initial speed)."""
        x, y, hd, v, queue, last = state
        queue = tuple(queue)
        if self.RD > 0:
            queue = queue + (action,)
            if len(queue) <= self.RD:
                eff = last
            else:
                eff = queue[0]
                queue = queue[1:]
        else:
            eff = action
        dx, dy = HEADINGS[hd]
        if eff in ("TURN_L", "TURN_R"):
            # Turn in place to a full stop (contract: heading changes
            # allowed; turning scrubs speed conservatively).
            nhd = _LEFT[hd] if eff == "TURN_L" else _RIGHT[hd]
            return (x, y, nhd, 0, queue, eff)
        if eff == "HOLD":
            v2 = 0
            path = [(x, y)]
        elif eff == "BRAKE":
            v2 = max(0, v - 1)
            path = [(x + dx * k, y + dy * k) for k in range(1, v2 + 1)]
        elif eff == "ACCEL":
            v2 = min(2, v + 1)
            if self.speed_limit and self._in_limit(x, y):
                v2 = min(v2, self.speed_limit["vmax"])
            path = [(x + dx * k, y + dy * k) for k in range(1, v2 + 1)]
        else:  # ADVANCE
            v2 = v
            if self.speed_limit and self._in_limit(x, y):
                v2 = min(v2, self.speed_limit["vmax"])
            path = [(x + dx * k, y + dy * k) for k in range(1, v2 + 1)]
        for (px, py) in path:
            if self.cell_blocked_static(px, py, walls):
                return None  # collision with wall/bounds: illegal move
        nx, ny = path[-1] if path else (x, y)
        return (nx, ny, hd, v2, queue, eff)

    def _in_limit(self, x, y):
        c = self.speed_limit["cells"]
        return c["x0"] <= x <= c["x1"] and c["y0"] <= y <= c["y1"]

    @functools.lru_cache(maxsize=None)
    def legal_actions(self, state, walls=frozenset()):
        out = []
        for a in ACTIONS:
            if self.step(state, a, walls) is not None:
                out.append(a)
        return tuple(out)

    @functools.lru_cache(maxsize=None)
    def footprint(self, state):
        """Swept cells of the CURRENT state (own cell ± U)."""
        x, y, _, _, _, _ = state
        cells = set()
        for dx in range(-self.U, self.U + 1):
            for dy in range(-self.U, self.U + 1):
                if self.in_bounds(x + dx, y + dy):
                    cells.add((x + dx, y + dy))
        return cells

    @functools.lru_cache(maxsize=None)
    def corridor_use(self, state0, state1):
        """Corridor sets touched when moving state0 -> state1 (uses the
        swept segment between them, inflated by U)."""
        x0, y0, _, _, _, _ = state0
        x1, y1, _, _, _, _ = state1
        seg = set()
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for k in range(n + 1):
            x = round(x0 + (x1 - x0) * k / n)
            y = round(y0 + (y1 - y0) * k / n)
            for dx in range(-self.U, self.U + 1):
                for dy in range(-self.U, self.U + 1):
                    seg.add((x + dx, y + dy))
        used = set()
        for i, cs in enumerate(self.corridor_sets):
            if seg & cs:
                used.add(i)
        return used
