"""RuleCoordinator: proposal/hash/coordination role. NEVER authorizes motion.

One OS process. JSON String topics (see msgspec.TOPICS). Steady clock
for all timers. Durable WAL append is the commit linearization point.
Restart recovers max durable epoch + fence from WAL, re-fences (+1),
resumes (never invents epochs).

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
from efrs_ros2.wal import wal_append, wal_read_epoch, wal_read_fence



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
    pubs = {k: node.create_publisher(String, t, 10)
            for k, t in M.TOPICS.items()
            if k in ("prepare", "commit", "renew", "reconcile_rep")}

    st = {"epoch": wal_read_epoch(wal_path),
          "fence": wal_read_fence(wal_path),
          "prepared": None, "votes": {}, "tick": 0,
          "vote_deadline": 0}
    # Liveness watch: last steady-ns state sighting per robot. Reach at
    # vote timeout = seen within REACH_MS (observable version of T0's
    # ground-truth reachability; identical harness for all protocols).
    REACH_MS = 2000
    last_seen: dict[str, int] = {}
    if wal_path.exists():
        st["fence"] += 1
        node.get_logger().info(
            f"restart: recovered epoch={st['epoch']} fence={st['fence']}")

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

    def propose(epoch: int):
        if st["prepared"] is not None or epoch != st["epoch"] + 1:
            return
        if args.protocol == "broadcast":
            st["epoch"] = epoch
            wal_append(wal_path, {"kind": "commit", "epoch": epoch,
                                  "hash": snap_hash(epoch),
                                  "fence": st["fence"]})
            pub("commit", M.commit_msg(f"tx{epoch}", epoch,
                                       snap_hash(epoch), st["fence"],
                                       10 ** 9, _re(epoch)))
            node.get_logger().info(f"broadcast epoch {epoch}")
            return
        st["prepared"] = {"epoch": epoch, "hash": snap_hash(epoch),
                          "fence": st["fence"], "txn": f"tx{epoch}"}
        st["votes"] = {}
        st["vote_deadline"] = (time.clock_gettime_ns(time.CLOCK_MONOTONIC)
                               + args.vote_timeout_ms * 10 ** 6)
        pub("prepare", M.prepare_msg(f"tx{epoch}", epoch,
                                     snap_hash(epoch), st["fence"],
                                     _re(epoch)))
        node.get_logger().info(f"propose epoch {epoch}")

    def on_admin(d):
        if d.get("op") == "propose":
            propose(int(d["epoch"]))
        elif d.get("op") == "fault":
            apply_admin_fault(shim, d, ("coordinator", "all"))

    def decide():
        """Commit iff every REACHABLE robot voted READY (T0 rule)."""
        reach = [r for r in robots
                 if now_ms() - last_seen.get(r, 0) <= REACH_MS]
        if not reach:
            node.get_logger().info("ABORT (no reachable robots)")
            st["prepared"] = None
            st["votes"] = {}
            return
        if set(st["votes"]) >= set(reach):
            if all(st["votes"].get(r) == "READY" for r in reach):
                ep = st["prepared"]["epoch"]
                st["epoch"] = ep
                wal_append(wal_path, {"kind": "commit", "epoch": ep,
                                      "hash": st["prepared"]["hash"],
                                      "fence": st["fence"]})
                pub("commit", M.commit_msg(
                    st["prepared"]["txn"], ep, st["prepared"]["hash"],
                    st["fence"], 1000, _re(ep)))
                node.get_logger().info(f"COMMIT epoch {ep}")
            else:
                node.get_logger().info(
                    f"ABORT epoch {st['prepared']['epoch']}")
            st["prepared"] = None
            st["votes"] = {}

    def now_ms() -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC) // 10 ** 6

    def on_state(d):
        if d.get("role") == "agent" and d.get("id") in robots:
            last_seen[d["id"]] = now_ms()

    def on_vote(d):
        d = shim.ingress(M.TOPICS["vote"], d, Shim.now_ns())
        if d is None or st["prepared"] is None:
            return
        if d.get("txn") != st["prepared"]["txn"]:
            return
        st["votes"][d["robot"]] = d["vote"]
        node.get_logger().info(
            f"vote {d['robot']}={d['vote']} votes={st['votes']}")
        decide()

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
        if (st["prepared"] is not None and time.clock_gettime_ns(
                time.CLOCK_MONOTONIC) > st["vote_deadline"]):
            node.get_logger().info("vote timeout: deciding by reachability")
            decide()

    subscribe_json(node, "/efrs/admin", on_admin)
    subscribe_json(node, M.TOPICS["vote"], on_vote)
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
