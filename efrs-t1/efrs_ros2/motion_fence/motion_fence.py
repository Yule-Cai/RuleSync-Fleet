"""MotionFence: LAST software boundary before motion is released.

One OS process per robot. Subscribes motion commands for its robot and
the paired agent's state. Releases a command ONLY if ALL hold at the
decision instant (steady clock):

    required_epoch == local committed epoch
    required_hash == local committed hash
    now <= lease_deadline_ns
    agent reconciled AND agent not holding

Baselines (broadcast/2pc) enforce NOTHING here either (faithful: the
missing gate is the defect under test) — but they still LOG every
command with the same verdict schema so matrices are comparable. Under
baselines every command is EXECUTED (verdict EXECUTED) with reason
"no-gate".

Otherwise: reject, emit safe stop/HOLD event with the exact reason.
Safety is enforced HERE, not only in the coordinator.

Args: --robot R1 --protocol {broadcast,2pc,efrs} --guard-ms 50
Publishes: /efrs/motion_event. Sink: event log (+ cmd_vel republish
only in the Phase-K witness via --cmdvel-topic).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from efrs_ros2 import msgspec as M
from efrs_ros2.rosutil import publish_json, subscribe_json
from efrs_ros2.shim import Shim



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
    ap.add_argument("--robot", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--guard-ms", type=int, default=50)
    ap.add_argument("--passthrough", action="store_true")
    ap.add_argument("--ignore-lease", action="store_true")
    ap.add_argument("--cmdvel-topic", default="")
    args = ap.parse_args()
    me = args.robot

    rclpy.init()
    node = Node(f"efrs_fence_{me.lower()}")
    shim = Shim(f"fence-{me}")
    agent_state: dict = {}

    pub_event = node.create_publisher(String, M.TOPICS["motion_event"], 10)
    pub_cmdvel = (node.create_publisher(String, args.cmdvel_topic, 10)
                  if args.cmdvel_topic else None)

    def now_ns() -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)

    def emit(cmd_id, required_epoch, verdict, reason):
        publish_json(pub_event, M.motion_event_msg(
            me, cmd_id, required_epoch, verdict, reason, now_ns()))
        if verdict == "EXECUTED" and pub_cmdvel is not None:
            publish_json(pub_cmdvel, {"v": M.WIRE, "cmd_id": cmd_id,
                                      "robot": me})

    def on_state(d):
        if d.get("role") == "agent" and d.get("id") == me:
            agent_state.clear()
            agent_state.update(d)

    def decide(cmd: dict):
        req_ep = int(cmd["required_epoch"])
        req_hash = str(cmd["required_hash"])
        cid = str(cmd["cmd_id"])
        if args.protocol != "efrs":
            emit(cid, req_ep, "EXECUTED", "no-gate")
            return
        if args.passthrough:
            emit(cid, req_ep, "EXECUTED", "ablation-no-gate")
            return
        if not agent_state:
            emit(cid, req_ep, "REJECTED", "no-agent-state")
            return
        if req_ep != int(agent_state.get("committed", -1)):
            emit(cid, req_ep, "REJECTED",
                 f"epoch-mismatch local={agent_state.get('committed')}")
            return
        if req_hash != str(agent_state.get("hash", "")):
            emit(cid, req_ep, "REJECTED", "hash-mismatch")
            return
        if not args.ignore_lease and now_ns() > int(
                agent_state.get("lease_deadline_ns", 0)):
            emit(cid, req_ep, "HELD", "lease-expired")
            return
        if not agent_state.get("reconciled", False):
            emit(cid, req_ep, "HELD", "unreconciled")
            return
        if agent_state.get("holding", False):
            emit(cid, req_ep, "HELD", "agent-holding")
            return
        emit(cid, req_ep, "EXECUTED", "gate-pass")

    def on_cmd(d):
        d = shim.ingress(M.TOPICS["motion_cmd"], d, Shim.now_ns())
        if d is None or d.get("robot") != me:
            return
        decide(d)

    subscribe_json(node, M.TOPICS["state"], on_state)
    subscribe_json(node, M.TOPICS["motion_cmd"], on_cmd)
    subscribe_json(node, "/efrs/admin",
                   lambda d: apply_admin_fault(shim, d, ("fence-" + me, "all"))
                   if d.get("op") == "fault" else None)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
