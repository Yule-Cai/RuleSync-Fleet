"""RuleCoordinator: proposal/hash/coordination role. NEVER authorizes motion.

T1.2 congestion-safe recovery (frozen design docs/EFRS_T12_PREREGISTRATION.md
§D): ONE PREPARE per attempt (no in-attempt retransmission); explicit
timeout abort at the frozen 1500 ms deadline; automatic new-generation
re-attempt (bounded-rate recovery, ~1 attempt / 1.6 s); ONE COMMIT per
durable decision (+ one replay on restart recovery, never a redrive
loop); one ACK per robot per txn (evidence only). Unchanged: txn_id,
unanimity-of-reachable threshold, REACH_MS, lease/heartbeat timing,
B_real, WAL linearization, restart disambiguation, never invent epochs,
never infer COMMIT from partial votes.

One OS process. JSON String topics (see msgspec.TOPICS). Steady clock
for all timers. Durable WAL append is the commit linearization point.
Restart recovers max durable epoch + fence from WAL, re-fences (+1),
resumes (never invents epochs); ABORTED gens never resurrect.

Args: --protocol {broadcast,2pc,efrs} --robots R1,R2,.. --wal PATH
      --heartbeat-ms 100 --vote-timeout-ms 500
Admin (out-of-band, unfaulted): /efrs/admin {op: propose, epoch} or
{op: fault, fault: {...}} (arms local egress shim, engineering only).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from efrs_ros2 import msgspec as M
from efrs_ros2.rosutil import publish_delayed, publish_json, subscribe_json
from efrs_ros2.msgspec import canonical_rules_hash as _ch
from efrs_ros2.msgspec import rules_for_epoch as _re
from efrs_ros2.shim import Shim
from efrs_ros2.wal import (wal_abort, wal_append, wal_commit,
                           wal_read_aborted_gens, wal_read_epoch,
                           wal_read_fence, wal_read_proposed_epochs)



def apply_admin_fault(shim, d, mine=()):
    """Arm or disarm (action == 'clear') a fault record."""
    f = d.get("fault", {})
    if f.get("target", "all") not in mine:
        return
    if f.get("action") == "clear" and "fid" in f:
        shim.disarm(f["fid"])
    elif "fid" in f:
        shim.arm(f)


def main() -> None:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String

    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--robots", required=True)
    ap.add_argument("--wal", required=True)
    ap.add_argument("--heartbeat-ms", type=int, default=100)
    ap.add_argument("--vote-timeout-ms", type=int, default=500)
    args = ap.parse_args()
    robots = args.robots.split(",")
    wal_path = Path(args.wal)

    rclpy.init()
    node = Node("efrs_coordinator")
    shim = Shim("coordinator")
    # T1.2 frozen queue sizing (§E): transaction-control topics use
    # CONTROL_DEPTH(N); telemetry stays at 10.
    cdepth = M.control_depth(len(robots))
    _ctrl = {"prepare", "commit", "abort", "vote", "ack"}
    pubs = {k: node.create_publisher(
                String, t, cdepth if k in _ctrl else 10)
            for k, t in M.TOPICS.items()
            if k in ("prepare", "commit", "renew", "reconcile_rep",
                     "abort", "txn_event")}

    def now_ns() -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)

    def now_ms() -> int:
        return now_ns() // 10 ** 6

    st = {"epoch": wal_read_epoch(wal_path),
          "fence": wal_read_fence(wal_path),
          "prepared": None, "votes": {}, "tick": 0,
          "vote_deadline": 0,
          # T1.1 attempt state (efrs only; baselines keep T1 behavior).
          "gen": {}, "aborted": wal_read_aborted_gens(wal_path),
          "rejected_terminal": set(), "pending": None,
          "reattempt_at": -1, "acked": {}, "late_ignored": 0}
    # Rebuild reject-terminal epochs from durable abort reasons.
    try:
        import json as _json
        with open(wal_path) as _fh:
            for _line in _fh:
                _line = _line.strip()
                if _line:
                    _rec = _json.loads(_line)
                    if _rec.get("kind") == "abort" and \
                            _rec.get("reason") == "reject":
                        st["rejected_terminal"].add(int(_rec["epoch"]))
    except FileNotFoundError:
        pass
    # Liveness watch: last steady-ns state sighting per robot. Reach at
    # vote timeout = seen within REACH_MS (observable version of T0's
    # ground-truth reachability; identical harness for all protocols).
    REACH_MS = 2000
    last_seen: dict[str, int] = {}
    if wal_path.exists():
        st["fence"] += 1
        node.get_logger().info(
            f"restart: recovered epoch={st['epoch']} fence={st['fence']}")
        # T1.1 restart disambiguation: resume COMMIT dissemination for a
        # durable commit (fresh unacked set); rebuild the pending logical
        # update from durable history (never resurrect an aborted gen,
        # never resurrect a reject-terminal epoch).
        proposed = wal_read_proposed_epochs(wal_path)
        committed_now = st["epoch"]
        if committed_now > 0:
            node.get_logger().info(
                f"restart: resuming COMMIT dissemination epoch "
                f"{committed_now}")
        uncomm = [e for e in proposed
                  if e == committed_now + 1
                  and e not in st["rejected_terminal"]]
        if uncomm:
            st["pending"] = min(uncomm)
            st["reattempt_at"] = now_ns()
            node.get_logger().info(
                f"restart: pending logical update epoch {st['pending']} "
                f"(aborted gens kept: "
                f"{sorted(g for (e, g) in st['aborted'] if e == st['pending'])})")
        if committed_now > 0:
            # T1.2 §D3: ONE COMMIT replay as restart recovery (not a
            # loop). Robots that miss it catch up via reconcile-pull;
            # robots that hold it no-op + ACK.
            pub("commit", M.commit_msg(
                M.txn_id(committed_now, snap_hash(committed_now),
                         st["gen"].get(committed_now, 0)),
                committed_now, snap_hash(committed_now), st["fence"],
                1000, _re(committed_now)))
            node.get_logger().info(
                f"restart: one COMMIT replay epoch {committed_now}")

    def snap_hash(epoch: int) -> str:
        return _ch(_re(epoch))

    def pub(topic_key, payload):
        publisher = pubs[topic_key]
        for _, p, dms in shim.egress(M.TOPICS[topic_key], payload,
                                     Shim.now_ns()):
            if dms:
                publish_delayed(node, publisher, p, dms)
            else:
                publish_json(publisher, p)

    def txn_emit(kind, txn, epoch, gen, detail=""):
        if args.protocol != "efrs":
            return
        pub("txn_event", M.txn_event_msg(kind, txn, epoch, gen, now_ns(),
                                         detail))

    def begin_attempt(epoch: int, gen: int):
        hx = snap_hash(epoch)
        txn = M.txn_id(epoch, hx, gen)
        st["prepared"] = {"epoch": epoch, "hash": hx,
                          "fence": st["fence"], "txn": txn, "gen": gen}
        st["votes"] = {}
        st["vote_deadline"] = now_ns() + args.vote_timeout_ms * 10 ** 6
        st["reattempt_at"] = -1
        pub("prepare", M.prepare_msg(txn, epoch, hx, st["fence"],
                                     _re(epoch)))
        node.get_logger().info(f"propose epoch {epoch} gen {gen}")
        txn_emit("attempt", txn, epoch, gen,
                 f"fence={st['fence']}")

    def propose(epoch: int):
        if epoch != st["epoch"] + 1:
            return
        if args.protocol == "broadcast":
            if st["prepared"] is not None:
                return
            wal_commit(wal_path, epoch, snap_hash(epoch), st["fence"])
            st["epoch"] = epoch
            pub("commit", M.commit_msg(f"tx{epoch}", epoch,
                                       snap_hash(epoch), st["fence"],
                                       10 ** 9, _re(epoch)))
            node.get_logger().info(f"broadcast epoch {epoch}")
            return
        if args.protocol != "efrs":
            if st["prepared"] is not None:
                return
            st["prepared"] = {"epoch": epoch, "hash": snap_hash(epoch),
                              "fence": st["fence"], "txn": f"tx{epoch}",
                              "gen": 0}
            st["votes"] = {}
            st["vote_deadline"] = now_ns() + args.vote_timeout_ms * 10 ** 6
            pub("prepare", M.prepare_msg(f"tx{epoch}", epoch,
                                         snap_hash(epoch), st["fence"],
                                         _re(epoch)))
            node.get_logger().info(f"propose epoch {epoch}")
            return
        # efrs T1.1: one active attempt per epoch; re-propose of the same
        # pending epoch starts a fresh generation (never resurrects an
        # aborted gen; reject-terminal epochs refuse).
        if st["prepared"] is not None:
            return
        if epoch in st["rejected_terminal"]:
            node.get_logger().info(
                f"refuse re-propose of reject-terminal epoch {epoch}")
            txn_emit("resurrect_refused", M.txn_id(epoch, snap_hash(epoch),
                                                  st["gen"].get(epoch, 0)),
                     epoch, st["gen"].get(epoch, 0), "reject-terminal")
            return
        if st["reattempt_at"] >= 0 and now_ns() < st["reattempt_at"]:
            return  # auto-reattempt timer owns the next attempt
        g = st["gen"].get(epoch, -1) + 1
        while (epoch, g) in st["aborted"]:
            g += 1
        st["gen"][epoch] = g
        st["pending"] = epoch
        st["reattempt_at"] = -1
        begin_attempt(epoch, g)

    def timeout_abort():
        p = st["prepared"]
        st["aborted"].add((p["epoch"], p["gen"]))
        wal_abort(wal_path, p["txn"], p["epoch"], p["gen"], p["hash"],
                  p["fence"], "timeout")
        pub("abort", M.abort_msg(p["txn"], p["epoch"], p["gen"],
                                 st["fence"]))
        node.get_logger().info(
            f"TIMEOUT-ABORT txn {p['txn']} (leaving round)")
        txn_emit("abort", p["txn"], p["epoch"], p["gen"], "timeout")
        st["prepared"] = None
        st["votes"] = {}
        # Automatic re-attempt exactly one heartbeat period later.
        st["reattempt_at"] = now_ns() + args.heartbeat_ms * 10 ** 6

    def reject_abort():
        p = st["prepared"]
        st["aborted"].add((p["epoch"], p["gen"]))
        st["rejected_terminal"].add(p["epoch"])
        st["pending"] = None
        wal_abort(wal_path, p["txn"], p["epoch"], p["gen"], p["hash"],
                  p["fence"], "reject")
        pub("abort", M.abort_msg(p["txn"], p["epoch"], p["gen"],
                                 st["fence"]))
        node.get_logger().info(
            f"REJECT-ABORT txn {p['txn']} (terminal for epoch "
            f"{p['epoch']})")
        txn_emit("abort", p["txn"], p["epoch"], p["gen"], "reject")
        st["prepared"] = None
        st["votes"] = {}

    def decide():
        """Commit iff every REACHABLE robot voted READY (T0 rule)."""
        reach = [r for r in robots
                 if now_ms() - last_seen.get(r, 0) <= REACH_MS]
        if not reach:
            node.get_logger().info("ABORT (no reachable robots)")
            if args.protocol == "efrs" and st["prepared"] is not None:
                timeout_abort()
            else:
                st["prepared"] = None
                st["votes"] = {}
            return
        if set(st["votes"]) >= set(reach):
            if all(st["votes"].get(r) == "READY" for r in reach):
                ep = st["prepared"]["epoch"]
                st["epoch"] = ep
                wal_commit(wal_path, ep, st["prepared"]["hash"],
                           st["fence"])
                pub("commit", M.commit_msg(
                    st["prepared"]["txn"], ep, st["prepared"]["hash"],
                    st["fence"], 1000, _re(ep)))
                node.get_logger().info(
                    f"COMMIT epoch {ep} txn {st['prepared']['txn']}")
                if args.protocol == "efrs":
                    txn_emit("commit", st["prepared"]["txn"], ep,
                             st["prepared"]["gen"],
                             f"votes={len(st['votes'])}")
                    st["acked"][ep] = set()
                    st["pending"] = None
                st["prepared"] = None
                st["votes"] = {}
            else:
                if args.protocol == "efrs":
                    reject_abort()
                else:
                    node.get_logger().info(
                        f"ABORT epoch {st['prepared']['epoch']}")
                    st["prepared"] = None
                    st["votes"] = {}

    def on_admin(d):
        if d.get("op") == "propose":
            propose(int(d["epoch"]))
        elif d.get("op") == "fault":
            apply_admin_fault(shim, d, ("coordinator", "all"))

    def on_vote(d):
        d = shim.ingress(M.TOPICS["vote"], d, Shim.now_ns())
        if d is None or st["prepared"] is None:
            return
        if args.protocol == "efrs" and \
                d.get("txn") != st["prepared"]["txn"]:
            # Late vote from a terminal/superseded attempt: ignore + count.
            st["late_ignored"] += 1
            node.get_logger().info(
                f"ignore late vote {d.get('robot')} txn {d.get('txn')} "
                f"(active {st['prepared']['txn']})")
            txn_emit("late_ignored", str(d.get("txn", "?")),
                     int(d.get("epoch", 0)), 0,
                     f"robot={d.get('robot')}")
            return
        if d.get("txn") != st["prepared"]["txn"]:
            return
        st["votes"][d["robot"]] = d["vote"]
        node.get_logger().info(
            f"vote {d['robot']}={d['vote']} votes={st['votes']}")
        decide()

    def on_ack(d):
        # T1.2 §D4: ACK is propagation evidence only (never a commit
        # precondition, never prunes anything). Counted for O metrics.
        d = shim.ingress(M.TOPICS["ack"], d, Shim.now_ns())
        if d is None or args.protocol != "efrs":
            return
        try:
            ep = M.txn_epoch(str(d.get("txn", "")))
        except ValueError:
            return
        st["acked"].setdefault(ep, set()).add(str(d.get("robot", "?")))

    def on_state(d):
        if d.get("role") == "agent" and d.get("id") in robots:
            last_seen[d["id"]] = now_ms()

    def on_reconcile_req(d):
        publish_json(
            pubs["reconcile_rep"],
            M.reconcile_rep_msg(d.get("robot", "?"), st["epoch"],
                                snap_hash(st["epoch"]), st["fence"],
                                _re(st["epoch"])))

    def heartbeat():
        st["tick"] += 1
        if args.protocol == "efrs":
            pub("renew", M.renew_msg(st["epoch"], st["fence"], st["tick"],
                                     _re(st["epoch"])))
        if args.protocol == "efrs" and st["prepared"] is not None:
            # T1.2 §D1: NO in-attempt PREPARE retransmission. One PREPARE
            # per attempt (published in begin_attempt); recovery runs
            # through new generations only (source-contract tested).
            if now_ns() > st["vote_deadline"]:
                node.get_logger().info(
                    "vote timeout: explicit abort, leaving round")
                timeout_abort()
        elif st["prepared"] is not None and now_ns() > st["vote_deadline"]:
            node.get_logger().info("vote timeout: deciding by reachability")
            decide()
        if args.protocol == "efrs" and st["prepared"] is None:
            # Automatic re-attempt of the pending logical update.
            if st["pending"] is not None and \
                    st["pending"] == st["epoch"] + 1 and \
                    st["reattempt_at"] >= 0 and \
                    now_ns() >= st["reattempt_at"]:
                g = st["gen"].get(st["pending"], -1) + 1
                while (st["pending"], g) in st["aborted"]:
                    g += 1
                st["gen"][st["pending"]] = g
                node.get_logger().info(
                    f"auto-reattempt epoch {st['pending']} gen {g}")
                txn_emit("reattempt",
                         M.txn_id(st["pending"],
                                  snap_hash(st["pending"]), g),
                         st["pending"], g, "")
                begin_attempt(st["pending"], g)
            # T1.2 §D3: NO COMMIT redrive loop (removed). Missed-COMMIT
            # catch-up runs through reconcile-pull only.

    subscribe_json(node, "/efrs/admin", on_admin)
    subscribe_json(node, M.TOPICS["vote"], on_vote, cdepth)
    subscribe_json(node, M.TOPICS["ack"], on_ack, cdepth)
    subscribe_json(node, M.TOPICS["state"], on_state)
    subscribe_json(node, M.TOPICS["reconcile_req"], on_reconcile_req)
    node.create_timer(args.heartbeat_ms / 1000.0, heartbeat)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
