"""EFRS wire message constructors/validators (ROS-free, pure Python).

Transport: JSON-encoded std_msgs/String on fixed topics (no colcon
codegen in the frozen container; field lists mirror efrs_ros2/msg/*.msg
1:1). Every constructor validates types/ranges and raises on violation.
Wire format version tag "efrs/1" on every message.
"""

from __future__ import annotations

import json as _json

WIRE = "efrs/1"


def canonical_rules_hash(rules) -> str:
    """Hex digest binding a hard-rule payload (I2 verification primitive).

    Rules: list of {rule_id, type, polygon[[x,y]...]}. Canonical form =
    JSON with sorted keys, compact separators.
    """
    import hashlib

    canon = _json.dumps(rules, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def rules_for_epoch(epoch: int):
    """Deterministic synthetic hard-rule payload per epoch (test fixture).

    Epoch e closes sector e%3 with a fixed polygon. Same on all honest
    nodes by construction; I2 faults mutate it in flight.
    """
    return [{"rule_id": f"keepout-e{epoch}",
             "type": 0,
             "polygon": [[float(epoch), 0.0], [float(epoch) + 1.0, 0.0],
                         [float(epoch) + 1.0, 1.0],
                         [float(epoch), 1.0]]}]

TOPICS = {
    "prepare": "/efrs/prepare",
    "vote": "/efrs/vote",
    "commit": "/efrs/commit",
    "renew": "/efrs/renew",
    "reconcile_req": "/efrs/reconcile_req",
    "reconcile_rep": "/efrs/reconcile_rep",
    "motion_cmd": "/efrs/motion_cmd",
    "motion_event": "/efrs/motion_event",
    "state": "/efrs/state",
    "fault": "/efrs/fault",
    # T1.1 additive topics (shim matches them by suffix automatically).
    "abort": "/efrs/abort",
    "ack": "/efrs/ack",
    "txn_event": "/efrs/txn_event",
}


def txn_id(epoch: int, snap_hash: str, gen: int) -> str:
    """T1.1 transaction attempt identity wire format.

    (candidate_epoch, snapshot_hash, attempt_generation); a retry of the
    same logical update keeps (epoch, hash) and increments gen.
    """
    if not isinstance(epoch, int) or epoch < 1:
        raise ValueError("epoch")
    if not isinstance(gen, int) or gen < 0:
        raise ValueError("gen")
    return f"tx{epoch}:{snap_hash}:g{gen}"


def parse_txn_id(txn: str):
    """Split a wire txn_id into (epoch, hash, gen); raises on violation."""
    try:
        head, _, g = str(txn).rpartition(":g")
        tx, _, h = head.partition(":")
        if not tx.startswith("tx"):
            raise ValueError("txn")
        return int(tx[2:]), h, int(g)
    except (ValueError, AttributeError):
        raise ValueError(f"bad txn_id: {txn!r}")


def txn_epoch(txn: str) -> int:
    return parse_txn_id(txn)[0]


def txn_gen(txn: str) -> int:
    return parse_txn_id(txn)[2]


def abort_msg(txn: str, epoch: int, gen: int, fence: int = 0):
    parse_txn_id(txn)
    if int(epoch) != txn_epoch(txn) or int(gen) != txn_gen(txn):
        raise ValueError("abort txn/epoch/gen mismatch")
    return {"v": WIRE, "txn": str(txn), "epoch": int(epoch),
            "gen": int(gen), "fence": int(fence)}


def ack_msg(robot: str, txn: str, epoch: int):
    parse_txn_id(txn)
    return {"v": WIRE, "robot": str(robot), "txn": str(txn),
            "epoch": int(epoch)}


def txn_event_msg(kind: str, txn: str, epoch: int, gen: int,
                  t_mono_ns: int, detail: str = ""):
    if kind not in ("attempt", "abort", "reattempt", "commit",
                    "commit_redrive", "late_ignored", "resurrect_refused"):
        raise ValueError("txn_event kind")
    parse_txn_id(txn)
    return {"v": WIRE, "kind": kind, "txn": str(txn), "epoch": int(epoch),
            "gen": int(gen), "t_mono_ns": int(t_mono_ns),
            "detail": str(detail)}


def _req(d: dict, keys):
    for k in keys:
        if k not in d:
            raise ValueError(f"missing field: {k}")
    return d


def prepare_msg(txn: str, epoch: int, snap_hash: str, fence: int,
                rules=None):
    if not isinstance(epoch, int) or epoch < 1:
        raise ValueError("epoch")
    return {"v": WIRE, "txn": str(txn), "epoch": epoch,
            "hash": str(snap_hash), "fence": int(fence),
            "rules": list(rules) if rules is not None else []}


def vote_msg(robot: str, txn: str, epoch: int, vote: str):
    if vote not in ("READY", "REJECT"):
        raise ValueError("vote")
    return {"v": WIRE, "robot": robot, "txn": str(txn), "epoch": int(epoch),
            "vote": vote}


def commit_msg(txn: str, epoch: int, snap_hash: str, fence: int,
               lease_ms: int, rules=None):
    _req({"t": txn}, ["t"])
    if lease_ms <= 0:
        raise ValueError("lease_ms")
    return {"v": WIRE, "txn": str(txn), "epoch": int(epoch),
            "hash": str(snap_hash), "fence": int(fence),
            "lease_ms": int(lease_ms),
            "rules": list(rules) if rules is not None else []}


def verify_rules(snap_hash: str, rules) -> bool:
    """True iff the payload canonically hashes to the claimed snapshot."""
    try:
        return canonical_rules_hash(list(rules)) == str(snap_hash)
    except Exception:
        return False


def renew_msg(epoch: int, fence: int, tick: int, rules=None,
              snap_hash: str = ""):
    if rules is None:
        claimed = str(snap_hash)
    else:
        claimed = canonical_rules_hash(list(rules))
    return {"v": WIRE, "epoch": int(epoch), "fence": int(fence),
            "tick": int(tick), "hash": claimed,
            "rules": list(rules) if rules is not None else []}


def reconcile_req_msg(robot: str):
    return {"v": WIRE, "robot": str(robot)}


def reconcile_rep_msg(robot: str, epoch: int, snap_hash: str, fence: int,
                        rules=None):
    return {"v": WIRE, "robot": str(robot), "epoch": int(epoch),
            "hash": str(snap_hash), "fence": int(fence),
            "rules": list(rules) if rules is not None else []}


def motion_cmd_msg(cmd_id: str, robot: str, required_epoch: int,
                   required_hash: str, vx: float = 0.0, vyaw: float = 0.0):
    return {"v": WIRE, "cmd_id": str(cmd_id), "robot": str(robot),
            "required_epoch": int(required_epoch),
            "required_hash": str(required_hash),
            "vx": float(vx), "vyaw": float(vyaw)}


def motion_event_msg(robot: str, cmd_id: str, required_epoch: int,
                     verdict: str, reason: str, t_mono_ns: int):
    if verdict not in ("EXECUTED", "HELD", "REJECTED"):
        raise ValueError("verdict")
    return {"v": WIRE, "robot": robot, "cmd_id": cmd_id,
            "required_epoch": int(required_epoch), "verdict": verdict,
            "reason": str(reason), "t_mono_ns": int(t_mono_ns)}


def state_msg(role: str, nid: str, prepared, committed: int, hash_: str,
              lease_deadline_ns, reconciled: bool, holding: bool,
              t_mono_ns: int):
    return {"v": WIRE, "role": role, "id": nid, "prepared": prepared,
            "committed": int(committed), "hash": str(hash_),
            "lease_deadline_ns": lease_deadline_ns,
            "reconciled": bool(reconciled), "holding": bool(holding),
            "t_mono_ns": int(t_mono_ns)}


def fault_msg(fid: str, target: str, action: str, match=None, params=None):
    """Control-plane fault arming. match: {msg_kind, epoch?} or {} (=all)."""
    if action not in ("drop", "duplicate", "delay_ms", "mutate", "clear"):
        raise ValueError("action")
    return {"v": WIRE, "fid": str(fid), "target": str(target),
            "action": action, "match": match or {},
            "params": params or {}}
