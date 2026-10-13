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

T1.2 local safety ledger (§F, frozen schema): EVERY authorization
decision is appended to --ledger (JSONL, flushed + fsync'd per record)
BEFORE an ACCEPT is published. Local filesystem only; never via ROS or
the fault shim. If the ledger is missing/corrupt the run is
evidence-incomplete (never PASS).
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
    # T1.2 §F: local audit ledger path (required — no ledger means no
    # safety evidence).
    ap.add_argument("--ledger", required=True)
    args = ap.parse_args()
    me = args.robot
    import json as _json
    import os as _os
    ledger_path = Path(args.ledger)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_fh = open(ledger_path, "a")
    ledger_fh.write(_json.dumps(
        {"ledger": "efrs-fence-v1", "robot": me,
         "opened_mono_ns": time.clock_gettime_ns(time.CLOCK_MONOTONIC)},
        sort_keys=True) + "\n")
    ledger_fh.flush()
    _os.fsync(ledger_fh.fileno())

    rclpy.init()
    node = Node(f"efrs_fence_{me.lower()}")
    shim = Shim(f"fence-{me}")
    agent_state: dict = {}

    pub_event = node.create_publisher(String, M.TOPICS["motion_event"], 10)
    pub_cmdvel = (node.create_publisher(String, args.cmdvel_topic, 10)
                  if args.cmdvel_topic else None)

    def now_ns() -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)

    def ledger_write(row: dict):
        ledger_fh.write(_json.dumps(row, sort_keys=True) + "\n")
        ledger_fh.flush()
        _os.fsync(ledger_fh.fileno())

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
        t = now_ns()

        def judge():
            if args.protocol != "efrs":
                return "EXECUTED", "no-gate"
            if args.passthrough:
                return "EXECUTED", "ablation-no-gate"
            if not agent_state:
                return "REJECTED", "no-agent-state"
            if req_ep != int(agent_state.get("committed", -1)):
                return ("REJECTED",
                        f"epoch-mismatch local={agent_state.get('committed')}")
            if req_hash != str(agent_state.get("hash", "")):
                return "REJECTED", "hash-mismatch"
            if not args.ignore_lease and t > int(
                    agent_state.get("lease_deadline_ns", 0)):
                return "HELD", "lease-expired"
            if not agent_state.get("reconciled", False):
                return "HELD", "unreconciled"
            if agent_state.get("holding", False):
                return "HELD", "agent-holding"
            return "EXECUTED", "gate-pass"

        verdict, reason = judge()
        # T1.2 §F: ledger BEFORE any ACCEPT is published/evidenced.
        ledger_write({
            "v": "efrs-ledger-v1",
            "monotonic_ns": t,
            "robot_id": me,
            "local_committed_epoch": agent_state.get("committed"),
            "local_committed_hash": agent_state.get("hash"),
            "lease_deadline_monotonic_ns": agent_state.get(
                "lease_deadline_ns"),
            "required_epoch": req_ep,
            "required_hash": req_hash,
            "cmd_id": cid,
            "decision": "ACCEPT" if verdict == "EXECUTED" else "REJECT",
            "reject_reason": None if verdict == "EXECUTED" else reason,
            "reconciled": agent_state.get("reconciled"),
            "holding": agent_state.get("holding"),
            "fence_seen": agent_state.get("fence_seen"),
        })
        emit(cid, req_ep, verdict, reason)

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
