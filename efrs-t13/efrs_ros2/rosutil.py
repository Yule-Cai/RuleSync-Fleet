"""Small ROS-side helpers (one-shot delayed publish, JSON pub/sub)."""

from __future__ import annotations

import json


def publish_json(publisher, payload: dict) -> None:
    from std_msgs.msg import String

    publisher.publish(String(data=json.dumps(payload, sort_keys=True)))


def publish_delayed(node, publisher, payload: dict, delay_ms: int):
    """One-shot delayed publish (timer kept alive on the node)."""
    from std_msgs.msg import String

    data = json.dumps(payload, sort_keys=True)
    if not hasattr(node, "_delay_timers"):
        node._delay_timers = []

    def _fire():
        publisher.publish(String(data=data))
        try:
            node._delay_timers.remove(timer)
        except ValueError:
            pass
        try:
            timer.cancel()
        except Exception:
            pass

    timer = node.create_timer(max(delay_ms, 1) / 1000.0, _fire)
    node._delay_timers.append(timer)


def subscribe_json(node, topic: str, callback, depth=10):
    """Subscribe with a depth int (default RELIABLE profile) or an
    explicit QoSProfile (e.g. txn_qos for transaction control)."""
    from std_msgs.msg import String

    def _cb(msg):
        try:
            callback(json.loads(msg.data))
        except Exception:
            return

    return node.create_subscription(String, topic, _cb, depth)


# T1.3 single transport change (§C): transaction-control topics use
# BEST_EFFORT + VOLATILE + KEEP_LAST at the frozen CONTROL_DEPTH.
# Everything else keeps the default (RELIABLE) profile.
TXN_CONTROL_TOPICS = frozenset(
    {"prepare", "vote", "abort", "commit", "ack"})


def txn_qos(depth: int):
    from rclpy.qos import (DurabilityPolicy, HistoryPolicy,
                           QoSProfile, ReliabilityPolicy)
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=int(depth))
