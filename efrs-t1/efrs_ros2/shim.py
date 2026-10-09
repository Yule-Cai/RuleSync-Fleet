"""Deterministic fault hooks (ROS-free core + thin ROS glue).

Every protocol publish/subscribe in T1 nodes passes through Shim.egress
/ Shim.ingress. The orchestrator arms faults via fault_msg records;
each armed fault has {id, action, match, params, armed_tick}. Actions:
drop / duplicate / delay_ms (timer queue) / mutate (content rewrite for
I2 tests) / clear (disarm). Match selects by ROS topic suffix (message
kind) and optional epoch. All hook decisions are appended to an audit
list (who/what/when) that the runner persists per run.

The ROS glue (RclpyShim) only needs: now_ns() and defer(ms, cb).
"""

from __future__ import annotations

import time


class Shim:
    def __init__(self, owner: str):
        self.owner = owner
        self.armed: list[dict] = []
        self.audit: list[dict] = []
        self.delayed: list[tuple] = []  # (release_ns, topic, payload)
        self._counter = 0

    def arm(self, fault: dict):
        # Idempotent by fid: admin repeats must not stack the effect.
        fid = fault.get("fid")
        self.armed = [f for f in self.armed if f.get("fid") != fid]
        self.armed.append(dict(fault))

    def disarm(self, fid: str):
        self.armed = [f for f in self.armed if f["fid"] != fid]

    def clear(self):
        self.armed = []

    def _match(self, fault, topic: str, payload: dict) -> bool:
        m = fault.get("match", {})
        kind = topic.rsplit("/", 1)[-1]
        if "msg_kind" in m and m["msg_kind"] != kind:
            return False
        if "epoch" in m and payload.get("epoch") != m["epoch"]:
            return False
        if "robot" in m and payload.get("robot") != m["robot"]:
            return False
        return True

    def _drop_draw(self, fault) -> bool:
        """Deterministic probabilistic drop (seeded by fid + counter)."""
        import random

        p = fault.get("params", {}).get("p", None)
        if p is None:
            return True
        self._counter += 1
        return random.Random(f"{fault.get('fid')}:{self._counter}") \
            .random() < float(p)

    def egress(self, topic: str, payload: dict, now_ns: int):
        """Return list of (topic, payload, delay_ms) to actually send."""
        out = [(topic, dict(payload), 0)]
        for f in list(self.armed):
            if not self._match(f, topic, payload):
                continue
            a = f["action"]
            self.audit.append({"t_ns": now_ns, "owner": self.owner,
                               "fid": f["fid"], "action": a,
                               "topic": topic})
            if a == "drop":
                if self._drop_draw(f):
                    return []
                continue
            if a == "duplicate":
                n = int(f.get("params", {}).get("times", 1))
                out = out + [(topic, dict(payload), 0)] * n
            elif a == "delay_ms":
                ms = int(f["params"]["ms"])
                out = [(t, p, d + ms) for (t, p, d) in out]
            elif a == "mutate":
                for (_, p, _) in out:
                    p.update(f.get("params", {}).get("set", {}))
        return out

    def ingress(self, topic: str, payload: dict, now_ns: int):
        """Return payload or None (dropped). Duplicate/delay on ingress
        are expressed by the caller re-injecting; keep it drop-only plus
        audit so semantics stay obvious."""
        for f in list(self.armed):
            if not self._match(f, topic, payload):
                continue
            a = f["action"]
            self.audit.append({"t_ns": now_ns, "owner": self.owner,
                               "fid": f["fid"], "action": "in-" + a,
                               "topic": topic})
            if a == "drop":
                if self._drop_draw(f):
                    return None
                continue
        return payload

    @staticmethod
    def now_ns() -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)
