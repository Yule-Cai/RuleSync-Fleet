"""RobotRuleAgent: per-robot prepared/committed/lease/reconcile state.

T1.1 eventual-heal extension (frozen design docs/EFRS_T11_PREREGISTRATION.md
§1.3): transaction attempt identity (epoch,hash,gen) carried in the txn
wire string; idempotent duplicate-PREPARE re-vote; generation supersede;
ABORT(txn) clears only the matching prepared (never committed state);
gen-aware COMMIT idempotency (same epoch+hash, any gen, is a no-op);
ACK on every COMMIT receipt; contact-sync tightening (RENEW never adopts —
adoption only via COMMIT/reconcile_rep; lease extends only for adopted
currency; newer-epoch renew triggers reconcile-pull; obsolete renew
ignored). --old-renewal preserves the exact pre-T1.1 loose path as the
A3 positive control. Unchanged: restart-UNRECONCILED, fence_seen,
hash/fence COMMIT guards, 2PC plain behavior, state @5Hz.

One OS process per robot. Handles PREPARE/COMMIT/ABORT/RENEW/reconcile with
per-protocol branches (flag --protocol, identical harness for all).
Restart: loads durable (committed, hash, fence_seen) from state file;
EFRS restarts UNRECONCILED (no motion) until reconcile completes.
Publishes state @5Hz with lease_deadline_ns (steady clock).

Args: --robot R1 --protocol {broadcast,2pc,efrs} --state-file PATH
      --lease-ms 1000
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from efrs_ros2 import msgspec as M
from efrs_ros2.rosutil import publish_delayed, publish_json, subscribe_json
from efrs_ros2.shim import Shim
from efrs_ros2.wal import robot_load, robot_save



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

    ap = argparse.ArgumentParser()
    ap.add_argument("--robot", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--lease-ms", type=int, default=1000)
    ap.add_argument("--no-lease-expiry", action="store_true")
    ap.add_argument("--old-renewal", action="store_true")
    # T1.2 §E: fleet size derives the control-topic queue depth.
    ap.add_argument("--fleet-size", type=int, default=3)
    args = ap.parse_args()
    me = args.robot
    state_path = Path(args.state_file)

    rclpy.init()
    node = Node(f"efrs_agent_{me.lower()}")
    shim = Shim(me)

    committed, hash_, fence_seen = robot_load(state_path)
    st = {"prepared": None, "committed": committed, "hash": hash_,
          "fence_seen": fence_seen,
          "lease_deadline_ns": 0, "reconciled": True, "holding": False,
          "voted": {},  # T1.1: txn -> last vote (duplicate recognition)
          "acked": set()}  # T1.2 §D4: txns already ACKed (at most one)
    if state_path.exists() and args.protocol == "efrs":
        st["reconciled"] = False
        node.get_logger().info(
            f"restart at epoch {committed}: UNRECONCILED, no motion")

    pubs = {k: node.create_publisher(
        __import__("std_msgs.msg", fromlist=["String"]).String, t,
        M.control_depth(args.fleet_size)
        if k in ("vote", "ack") else 10)
        for k, t in M.TOPICS.items() if k in ("vote", "reconcile_req",
                                              "ack")}

    def now_ns() -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)

    def pub(topic_key, payload):
        publisher = pubs[topic_key]
        for _, p, dms in shim.egress(M.TOPICS[topic_key], payload,
                                     Shim.now_ns()):
            if dms:
                publish_delayed(node, publisher, p, dms)
            else:
                publish_json(publisher, p)

    def persist():
        robot_save(state_path, st["committed"], st["hash"],
                   st["fence_seen"])

    def txn_parsed(txn_str):
        try:
            return M.parse_txn_id(str(txn_str))
        except ValueError:
            return None

    def on_prepare(d):
        d = shim.ingress(M.TOPICS["prepare"], d, Shim.now_ns())
        if d is None or args.protocol == "broadcast":
            return
        if d["epoch"] <= st["committed"]:
            pub("vote", M.vote_msg(me, d.get("txn", ""), d["epoch"],
                                   "REJECT"))
            return
        if args.protocol == "efrs" and d.get("fence", 0) < st["fence_seen"]:
            pub("vote", M.vote_msg(me, d.get("txn", ""), d["epoch"],
                                   "REJECT"))
            return
        if args.protocol == "efrs":
            from efrs_ros2.msgspec import verify_rules as _vr
            if not _vr(str(d.get("hash", "")), d.get("rules", [])):
                node.get_logger().info("reject PREPARE: hash mismatch")
                pub("vote", M.vote_msg(me, d.get("txn", ""),
                                       d["epoch"], "REJECT"))
                return
            # T1.1 txn rules: identical txn -> idempotent re-vote (same
            # vote as before, state untouched); older generation ->
            # ignore; newer generation supersedes.
            t = str(d.get("txn", ""))
            par = txn_parsed(t)
            if par is None:
                node.get_logger().info(
                    f"ignore PREPARE with malformed txn {t!r}")
                return
            cur = st["prepared"]
            if cur is not None and str(cur.get("txn", "")) == t:
                # T1.2 §D2: duplicate PREPARE(txn) is idempotently
                # recognized and emits NOTHING further (at most one VOTE
                # per robot per txn_id; no vote flooding).
                node.get_logger().info(f"duplicate PREPARE {t} recognized")
                return
            if cur is not None:
                cpar = txn_parsed(str(cur.get("txn", "")))
                if cpar is not None and (par[0], par[1]) == (cpar[0],
                                                             cpar[1]) \
                        and par[2] <= cpar[2]:
                    node.get_logger().info(
                        f"ignore superseded PREPARE {t} "
                        f"(prepared {cur.get('txn')})")
                    return
                node.get_logger().info(
                    f"supersede {cur.get('txn')} with PREPARE {t}")
            st["prepared"] = dict(d)
            st["voted"][t] = "READY"
            pub("vote", M.vote_msg(me, t, d["epoch"], "READY"))
            return
        st["prepared"] = dict(d)
        pub("vote", M.vote_msg(me, d.get("txn", ""), d["epoch"], "READY"))

    def on_abort(d):
        # T1.1: ABORT clears ONLY the matching prepared; committed state
        # is never touched by an abort (asserted by I1).
        d = shim.ingress(M.TOPICS["abort"], d, Shim.now_ns())
        if d is None or args.protocol != "efrs":
            return
        t = str(d.get("txn", ""))
        cur = st["prepared"]
        if cur is not None and str(cur.get("txn", "")) == t:
            st["prepared"] = None
            node.get_logger().info(f"cleared prepared on ABORT {t}")
        else:
            node.get_logger().info(
                f"ignore ABORT {t} (prepared "
                f"{None if cur is None else cur.get('txn')})")

    def apply(epoch: int, hash__: str, fence: int, lease_ms: int):
        st["committed"] = epoch
        st["hash"] = hash__
        st["fence_seen"] = max(st["fence_seen"], fence)
        if args.protocol == "efrs" and not args.no_lease_expiry:
            st["lease_deadline_ns"] = now_ns() + lease_ms * 10 ** 6
        elif args.protocol != "efrs":
            st["lease_deadline_ns"] = 10 ** 30
        st["prepared"] = None
        persist()
        node.get_logger().info(f"committed epoch {epoch} hash {hash__}")

    def send_ack(txn_str, epoch: int):
        # T1.2 §D4: at most one ACK per robot per txn_id.
        t = str(txn_str)
        if t in st["acked"]:
            return
        st["acked"].add(t)
        pub("ack", M.ack_msg(me, t, int(epoch)))

    def on_commit(d):
        d = shim.ingress(M.TOPICS["commit"], d, Shim.now_ns())
        if d is None:
            return
        ep = int(d["epoch"])
        if args.protocol == "broadcast":
            if ep >= st["committed"]:
                apply(ep, d.get("hash", f"h{ep}"), d.get("fence", 0),
                      10 ** 12)
            return
        if args.protocol == "2pc":
            # Faithful plain-2PC: epoch match only; late older COMMITs
            # roll back (the T0-demonstrated bug).
            apply(ep, d.get("hash", f"h{ep}"), d.get("fence", 0), 10 ** 12)
            return
        if ep < st["committed"]:
            node.get_logger().info(f"reject stale COMMIT epoch {ep}")
            return
        if args.protocol == "efrs":
            from efrs_ros2.msgspec import verify_rules as _vr2
            if not _vr2(str(d.get("hash", "")), d.get("rules", [])):
                node.get_logger().info("reject COMMIT: hash mismatch")
                return
            # T1.1: same (epoch, hash) already applied, any generation ->
            # idempotent no-op (never a rollback), still ACK.
            if ep == st["committed"] and \
                    str(d.get("hash", "")) == st["hash"]:
                node.get_logger().info(
                    f"idempotent COMMIT {d.get('txn')} (already epoch "
                    f"{ep})")
                send_ack(str(d.get("txn", "")), ep)
                return
            if ep == st["committed"]:
                node.get_logger().info(
                    f"reject conflicting COMMIT epoch {ep} "
                    f"(hash differs from committed)")
                return
        if d.get("fence", 0) < st["fence_seen"]:
            node.get_logger().info("reject fenced-out COMMIT")
            return
        apply(ep, d["hash"], d.get("fence", 0), int(d.get("lease_ms", 1000)))
        if args.protocol == "efrs":
            send_ack(str(d.get("txn", "")), ep)

    def on_renew(d):
        d = shim.ingress(M.TOPICS["renew"], d, Shim.now_ns())
        if d is None or args.protocol != "efrs":
            return
        if d.get("fence", 0) < st["fence_seen"]:
            return
        if args.old_renewal:
            # A3 positive control: exact pre-T1.1 loose path (adopt any
            # newer epoch; extend lease unconditionally). Reproduces the
            # T0 contact-renewal bug; final EFRS must not.
            if int(d["epoch"]) > st["committed"]:
                from efrs_ros2.msgspec import verify_rules as _vr3
                if not _vr3(str(d.get("hash", "")), d.get("rules", [])):
                    node.get_logger().info("ignore RENEW: hash mismatch")
                    return
                st["committed"] = int(d["epoch"])
                st["hash"] = str(d.get("hash", st["hash"]))
                st["prepared"] = None
                node.get_logger().info(
                    f"adopt renewal epoch {st['committed']}")
                persist()
            node.get_logger().info("old-renewal: lease only, no adopt")
            st["fence_seen"] = max(st["fence_seen"], d.get("fence", 0))
            if not args.no_lease_expiry:
                st["lease_deadline_ns"] = now_ns() + args.lease_ms * 10 ** 6
            if not st["reconciled"]:
                st["reconciled"] = True
                node.get_logger().info("reconciled via renewal")
            return
        # T1.1 contact-sync (§J): RENEW never adopts. Newer-epoch renew
        # triggers reconcile-pull (authoritative install via rep);
        # adopted currency extends the lease; obsolete renew ignored.
        ep = int(d["epoch"])
        if ep > st["committed"]:
            node.get_logger().info(
                f"newer-epoch RENEW {ep} (committed {st['committed']}): "
                f"reconcile-pull, no adopt")
            request_reconcile()
            return
        if ep < st["committed"]:
            node.get_logger().info(
                f"ignore obsolete RENEW {ep} (committed {st['committed']})")
            return
        st["fence_seen"] = max(st["fence_seen"], d.get("fence", 0))
        if not args.no_lease_expiry:
            st["lease_deadline_ns"] = now_ns() + args.lease_ms * 10 ** 6
        if not st["reconciled"]:
            st["reconciled"] = True
            node.get_logger().info("reconciled via renewal")

    def on_reconcile_rep(d):
        d = shim.ingress(M.TOPICS["reconcile_rep"], d, Shim.now_ns())
        if d is None or d.get("robot") != me:
            return
        if int(d["epoch"]) >= st["committed"]:
            if args.protocol == "efrs":
                from efrs_ros2.msgspec import verify_rules as _vr4

                if not _vr4(str(d.get("hash", "")), d.get("rules", [])):
                    node.get_logger().info(
                        "ignore reconcile_rep: hash mismatch")
                    return
            st["committed"] = int(d["epoch"])
            st["hash"] = str(d["hash"])
            st["prepared"] = None
            persist()
        if args.protocol == "efrs":
            st["fence_seen"] = max(st["fence_seen"], int(d.get("fence", 0)))
            st["lease_deadline_ns"] = now_ns() + args.lease_ms * 10 ** 6
        st["reconciled"] = True
        st["holding"] = False
        node.get_logger().info(f"reconciled at epoch {st['committed']}")

    def request_reconcile():
        pub("reconcile_req", M.reconcile_req_msg(me))

    def pub_state(payload):
        for _, p, dms in shim.egress(M.TOPICS["state"], payload,
                                     Shim.now_ns()):
            if dms:
                publish_delayed(node, pubs_state, p, dms)
            else:
                publish_json(pubs_state, p)

    def state_tick():
        # Re-request reconcile while unreconciled (1 Hz equivalent: every
        # 5th 200ms tick).
        state_tick.n = getattr(state_tick, "n", 0) + 1
        if args.protocol == "efrs" and not st["reconciled"] and \
                state_tick.n % 5 == 0:
            request_reconcile()
        if args.protocol == "efrs":
            lease_bad = (not args.no_lease_expiry) and (
                now_ns() > st["lease_deadline_ns"])
            st["holding"] = (not st["reconciled"]) or lease_bad
        pub_state(
            M.state_msg("agent", me,
                        st["prepared"]["epoch"]
                        if st["prepared"] else None,
                        st["committed"], st["hash"],
                        st["lease_deadline_ns"], st["reconciled"],
                        st["holding"], now_ns(),
                        fence_seen=st["fence_seen"]))

    pubs_state = node.create_publisher(
        __import__("std_msgs.msg", fromlist=["String"]).String,
        M.TOPICS["state"], 10)
    cdepth = M.control_depth(args.fleet_size)
    subscribe_json(node, M.TOPICS["prepare"], on_prepare, cdepth)
    subscribe_json(node, M.TOPICS["abort"], on_abort, cdepth)
    subscribe_json(node, M.TOPICS["commit"], on_commit, cdepth)
    subscribe_json(node, M.TOPICS["renew"], on_renew)
    subscribe_json(node, M.TOPICS["reconcile_rep"], on_reconcile_rep)
    subscribe_json(node, "/efrs/admin",
                   lambda d: apply_admin_fault(shim, d, (me, "all"))
                   if d.get("op") == "fault" else None)
    if args.protocol == "efrs" and not st["reconciled"]:
        request_reconcile()
    node.create_timer(0.2, state_tick)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
