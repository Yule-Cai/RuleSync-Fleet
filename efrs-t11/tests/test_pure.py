"""Unit proofs for EFRS pure parts (msgspec/shim/wal). No ROS needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from efrs_ros2 import msgspec as M
from efrs_ros2.shim import Shim
from efrs_ros2 import wal as W


def test_msgspec_validation():
    M.prepare_msg("tx1", 1, "h1", 2)
    M.vote_msg("R1", "tx1", 1, "READY")
    M.commit_msg("tx1", 1, "h1", 2, 1000)
    M.motion_cmd_msg("c1", "R1", 0, "h0")
    for bad in (lambda: M.prepare_msg("t", 0, "h", 1),
                lambda: M.vote_msg("R1", "t", 1, "MAYBE"),
                lambda: M.commit_msg("t", 1, "h", 1, 0),
                lambda: M.motion_event_msg("R1", "c", 0, "VANISHED", "x", 1),
                lambda: M.fault_msg("f", "R1", "vaporize")):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("invalid message accepted")


def test_shim_drop_duplicate_delay():
    s = Shim("t")
    p = {"epoch": 1}
    assert s.egress("/efrs/commit", dict(p), 0) != []
    s.arm({"fid": "d1", "action": "drop", "match": {"msg_kind": "commit"},
           "params": {}})
    assert s.egress("/efrs/commit", dict(p), 0) == []
    assert s.egress("/efrs/prepare", dict(p), 0) != []
    s.clear()
    s.arm({"fid": "d2", "action": "duplicate",
           "match": {"msg_kind": "commit"}, "params": {"times": 2}})
    assert len(s.egress("/efrs/commit", dict(p), 0)) == 3
    s.clear()
    s.arm({"fid": "d3", "action": "delay_ms",
           "match": {"msg_kind": "commit"}, "params": {"ms": 250}})
    out = s.egress("/efrs/commit", dict(p), 0)
    assert out[0][2] == 250
    assert len(s.audit) == 3


def test_shim_robot_match_and_probabilistic():
    s = Shim("t")
    s.arm({"fid": "p1", "action": "drop", "match": {"robot": "R3"},
           "params": {}})
    assert s.egress("/efrs/vote", {"robot": "R3"}, 0) == []
    assert s.egress("/efrs/vote", {"robot": "R1"}, 0) != []
    s.clear()
    s.arm({"fid": "r1", "action": "drop",
           "match": {"msg_kind": "commit"}, "params": {"p": 0.5}})
    n = sum(1 for _ in range(200)
            if s.egress("/efrs/commit", {"epoch": 1}, 0) == [])
    assert 60 < n < 140, n
    again = Shim("t")
    again.arm({"fid": "r1", "action": "drop",
               "match": {"msg_kind": "commit"}, "params": {"p": 0.5}})
    n2 = sum(1 for _ in range(200)
             if again.egress("/efrs/commit", {"epoch": 1}, 0) == [])
    assert n == n2  # deterministic per fid+counter


def test_shim_mutate_and_disarm():
    s = Shim("t")
    s.arm({"fid": "m1", "action": "mutate",
           "match": {"msg_kind": "commit"}, "params": {"set": {"hash": "hx"}}})
    out = s.egress("/efrs/commit", {"epoch": 1, "hash": "h1"}, 0)
    assert out[0][1]["hash"] == "hx"
    assert s.ingress("/efrs/commit", {"epoch": 1}, 0) is not None
    s.disarm("m1")
    out = s.egress("/efrs/commit", {"epoch": 1, "hash": "h1"}, 0)
    assert out[0][1]["hash"] == "h1"


def test_wal(tmp_path=None):
    import tempfile

    d = tempfile.mkdtemp()
    p = Path(d) / "w.jsonl"
    assert W.wal_read_epoch(p) == 0
    W.wal_append(p, {"kind": "commit", "epoch": 1, "fence": 3})
    W.wal_append(p, {"kind": "commit", "epoch": 2, "fence": 4})
    assert W.wal_read_epoch(p) == 2
    assert W.wal_read_fence(p) == 4
    rp = Path(d) / "r.json"
    assert W.robot_load(rp) == (0, "h0", 0)
    W.robot_save(rp, 2, "h2", 5)
    assert W.robot_load(rp) == (2, "h2", 5)


def test_txn_identity():
    # T1.1: (epoch, hash, gen) wire format; retry keeps epoch+hash,
    # increments gen; malformed rejected.
    t0 = M.txn_id(3, "abc123", 0)
    assert (M.txn_epoch(t0), M.txn_gen(t0)) == (3, 0)
    t1 = M.txn_id(3, "abc123", 1)
    assert M.parse_txn_id(t1) == (3, "abc123", 1)
    assert t0 != t1
    for bad in ("tx3", "tx3:abc123", "txX:abc123:g1", "tx3:abc123:g",
                "3:abc123:g0", "", None, 123):
        try:
            M.parse_txn_id(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"bad txn accepted: {bad!r}")
    for bad in (lambda: M.txn_id(0, "h", 0),
                lambda: M.txn_id(1, "h", -1),
                lambda: M.abort_msg(t0, 4, 0),
                lambda: M.abort_msg(t0, 3, 1),
                lambda: M.txn_event_msg("wedged", t0, 3, 0, 1)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("invalid txn message accepted")
    a = M.abort_msg(t0, 3, 0, fence=2)
    assert (a["txn"], a["epoch"], a["gen"], a["fence"]) == (t0, 3, 0, 2)
    k = M.ack_msg("R2", t1, 3)
    assert (k["robot"], k["txn"], k["epoch"]) == ("R2", t1, 3)
    e = M.txn_event_msg("abort", t0, 3, 0, 999, "timeout")
    assert (e["kind"], e["t_mono_ns"]) == ("abort", 999)


def test_wal_abort_disambiguation():
    # T1.1 §I: aborts never inflate the recovered epoch; aborted gens
    # are queryable; commits carry on as before.
    import tempfile

    d = tempfile.mkdtemp()
    p = Path(d) / "w.jsonl"
    W.wal_commit(p, 1, "h1", 1)
    W.wal_abort(p, M.txn_id(2, "h2", 0), 2, 0, "h2", 1, "timeout")
    W.wal_abort(p, M.txn_id(2, "h2", 1), 2, 1, "h2", 1, "reject")
    assert W.wal_read_epoch(p) == 1
    assert W.wal_read_fence(p) == 1
    assert W.wal_read_aborted_gens(p) == {(2, 0), (2, 1)}
    assert W.wal_read_proposed_epochs(p) == [1, 2]


if __name__ == "__main__":
    test_msgspec_validation()
    test_shim_drop_duplicate_delay()
    test_shim_robot_match_and_probabilistic()
    test_shim_mutate_and_disarm()
    test_wal()
    test_txn_identity()
    test_wal_abort_disambiguation()
    print("efrs pure proofs passed")
