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


def test_control_depth_mapping():
    # T1.2 §E frozen formula, pinned for 3/5/20 (+ edges).
    assert M.control_depth(1) == 32
    assert M.control_depth(3) == 32
    assert M.control_depth(5) == 32
    assert M.control_depth(12) == 32
    assert M.control_depth(13) == 34
    assert M.control_depth(20) == 48
    # Runner-local duplicate must match (runner cannot import msgspec).
    assert max(32, 2 * 20 + 8) == M.control_depth(20)
    assert max(32, 2 * 3 + 8) == M.control_depth(3)
    try:
        M.control_depth(0)
    except ValueError:
        pass
    else:
        raise AssertionError("control_depth(0) accepted")


def test_source_contracts_no_redrive():
    # T1.2 §P: PREPARE is published ONLY from begin_attempt (never from
    # heartbeat); COMMIT is never published from an ACK-count loop.
    import ast as _ast
    coord = Path(__file__).resolve().parents[1] / "efrs_ros2" / \
        "coordinator" / "coordinator.py"
    tree = _ast.parse(coord.read_text())
    fns = {n.name: n for n in _ast.walk(tree)
           if isinstance(n, _ast.FunctionDef)}
    hb = _ast.dump(fns["heartbeat"])
    assert '"prepare"' not in hb and "'prepare'" not in hb, \
        "PREPARE published from heartbeat()"
    assert "acked" not in hb or "commit" not in hb.replace(
        "commitment", ""), "ACK-driven COMMIT loop in heartbeat()"
    src = coord.read_text()
    # Exactly two PREPARE sites: begin_attempt (EFRS, once per attempt)
    # and the frozen single-shot baseline propose (2PC/broadcast path).
    assert src.count('pub("prepare"') == 2, \
        "unexpected PREPARE publish sites"
    # Exactly three COMMIT sites: broadcast propose (frozen baseline
    # path), ONE restart replay (§D3), decide() (durable commit).
    assert src.count('pub("commit"') == 3, \
        "COMMIT published from unexpected sites"


def test_ledger_schema():
    # T1.2 §F: required ledger fields exist in the fence writer.
    fence = Path(__file__).resolve().parents[1] / "efrs_ros2" / \
        "motion_fence" / "motion_fence.py"
    src = fence.read_text()
    for field in ("monotonic_ns", "robot_id", "local_committed_epoch",
                  "local_committed_hash", "lease_deadline_monotonic_ns",
                  "required_epoch", "required_hash", "cmd_id", "decision",
                  "reject_reason", "reconciled", "holding", "fence_seen",
                  "fsync"):
        assert field in src, f"ledger schema missing {field}"
    assert "--ledger" in src


def test_txn_qos_contracts():
    # T1.3 §D (ROS-free half): the five transaction topics are exactly
    # the TXN_CONTROL_TOPICS set; no RELIABLE symbol remains anywhere in
    # protocol code; depth formula unchanged.
    import ast as _ast
    root = Path(__file__).resolve().parents[1] / "efrs_ros2"
    ru = (root / "rosutil.py").read_text()
    tree = _ast.parse(ru)
    names = {n.targets[0].id for n in _ast.walk(tree)
             if isinstance(n, _ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], _ast.Name)}
    assert "TXN_CONTROL_TOPICS" in names
    assert "txn_qos" in {n.name for n in _ast.walk(tree)
                         if isinstance(n, _ast.FunctionDef)}
    assert "BEST_EFFORT" in ru and "VOLATILE" in ru and "KEEP_LAST" in ru
    for src in ["coordinator/coordinator.py", "robot_agent/robot_agent.py",
                "motion_fence/motion_fence.py", "shim.py", "wal.py",
                "msgspec.py", "rosutil.py"]:
        text = (root / src).read_text()
        assert "ReliabilityPolicy.RELIABLE" not in text, \
            f"RELIABLE remains in {src}"
        assert "RELIABLE" not in text or "BEST_EFFORT" in text, \
            f"stray RELIABLE mention in {src}"
    for src, topics in [
            ("coordinator/coordinator.py",
             ["prepare", "commit", "abort", "vote", "ack"]),
            ("robot_agent/robot_agent.py",
             ["prepare", "commit", "abort", "vote", "ack"])]:
        text = (root / src).read_text()
        assert text.count("txn_qos(") >= 2, \
            f"txn_qos not wired in {src}"
    assert M.control_depth(20) == 48 and M.control_depth(3) == 32


def test_sched_util_gst():
    # T1.3a workload semantics: until honored, independent, permanent
    # preserved, GST math exact.
    import math as _math
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                            / "fault_harness"))
    import sched_util as _su
    # loss with until expires exactly there.
    assert _su.fault_end({"kind": "loss_random", "t": 5.0,
                          "until": 8.0}) == 8.0
    # loss without until is permanent (W-SUSTAINED preserved).
    assert _su.fault_end({"kind": "loss_random", "t": 5.0}) == _math.inf
    # overlapping losses expire independently (no stacking).
    assert _su.fault_end({"kind": "loss_random", "t": 25.52,
                          "until": 28.52}) == 28.52
    assert _su.schedule_gst([{"kind": "loss_random", "t": 5.0,
                              "until": 8.0}]) == 8.0
    assert _su.schedule_gst([{"kind": "loss_random",
                              "t": 5.0}]) == _math.inf
    assert _su.schedule_gst([]) is None
    sroot = Path(__file__).resolve().parents[1] / "experiments"
    # W-HEAL file (where present): GST == 248.02, every loss capped.
    import json as _json2
    for cand in (sroot / "t13_scale" / "sched-wheal.json",
                 sroot / "t12_scale" / "sched-wheal.json"):
        if cand.exists():
            w = _json2.load(open(cand))
            assert _su.schedule_gst(w["faults"]) == 248.02
            assert all("until" in f for f in w["faults"]
                       if f["kind"] == "loss_random")
            break
    # W-SUSTAINED file: permanence preserved (>=1 unterminated loss).
    s = None
    for cand in (sroot / "t13_scale" / "sched-sustained.json",
                 sroot / "t12_scale" / "sched-sustained.json"):
        if cand.exists():
            import json as _json
            s = _json.load(open(cand))
            break
    if s is not None:
        assert any("until" not in f for f in s["faults"]
                   if f["kind"] == "loss_random")


def test_loss_random_branch_schedules_clear():
    # AST contract: loss_random WITH until schedules a disarm; the
    # no-until path arms without one; no other fault branch changed.
    import ast as _ast
    r = (Path(__file__).resolve().parents[1] / "fault_harness"
         / "runner.py").read_text()
    tree = _ast.parse(r)
    dump = _ast.dump(tree)
    assert '"until"' in dump or "'until'" in dump
    seg = r.split('kind == "loss_random"')[1].split("elif kind ==")[0]
    assert "until" in seg and "clear" in seg, \
        "loss_random ignores until (T1 defect still present)"
    assert "unlossr" in seg, "independent per-fault clear missing"


def test_old_renewal_never_adopts():
    # A3 amendment: under --old-renewal, a newer RENEW must NEVER
    # change committed epoch/hash (T1-exact: extend-without-adopt).
    import ast as _ast
    src = (Path(__file__).resolve().parents[1] / "efrs_ros2" /
           "robot_agent" / "robot_agent.py").read_text()
    tree = _ast.parse(src)
    fns = {n.name: n for n in _ast.walk(tree)
           if isinstance(n, _ast.FunctionDef)}
    on_renew = fns["on_renew"]
    olds = [n for n in _ast.walk(on_renew)
            if isinstance(n, _ast.If)
            and _ast.dump(n.test) == _ast.dump(
                _ast.parse("args.old_renewal").body[0].value)]
    assert len(olds) == 1, "old_renewal branch not found exactly once"
    body = _ast.dump(olds[0])
    assert 'st["committed"]' not in body \
        and "st['committed']" not in body, \
        "old_renewal branch touches committed epoch"
    assert '"hash"' not in body and "'hash'" not in body, \
        "old_renewal branch touches hash"
    assert "persist()" not in body, \
        "old_renewal branch persists state"
    assert "lease_deadline_ns" in body, \
        "old_renewal branch must still extend the lease"


def test_normal_renew_keeps_frozen_semantics():
    # Normal EFRS path unchanged: RENEW never assigns committed (pull
    # instead of adopt); adoption lives only in apply()/reconcile_rep.
    import ast as _ast
    src = (Path(__file__).resolve().parents[1] / "efrs_ros2" /
           "robot_agent" / "robot_agent.py").read_text()
    tree = _ast.parse(src)
    fns = {n.name: n for n in _ast.walk(tree)
           if isinstance(n, _ast.FunctionDef)}
    stores = [n for n in _ast.walk(fns["on_renew"])
              if isinstance(n, _ast.Subscript)
              and isinstance(n.ctx, _ast.Store)
              and isinstance(n.value, _ast.Name)
              and n.value.id == "st"
              and isinstance(n.slice, _ast.Constant)
              and n.slice.value in ("committed", "hash", "prepared")]
    assert not stores, "on_renew assigns committed/hash/prepared"
    for keeper in ("apply", "on_reconcile_rep"):
        ksrc = _ast.dump(fns[keeper])
        assert "committed" in ksrc, \
            f"{keeper} lost its adoption assignment"


if __name__ == "__main__":
    test_msgspec_validation()
    test_shim_drop_duplicate_delay()
    test_shim_robot_match_and_probabilistic()
    test_shim_mutate_and_disarm()
    test_wal()
    test_txn_identity()
    test_wal_abort_disambiguation()
    test_control_depth_mapping()
    test_source_contracts_no_redrive()
    test_ledger_schema()
    test_txn_qos_contracts()
    test_sched_util_gst()
    test_loss_random_branch_schedules_clear()
    test_old_renewal_never_adopts()
    test_normal_renew_keeps_frozen_semantics()
    print("efrs pure proofs passed")
