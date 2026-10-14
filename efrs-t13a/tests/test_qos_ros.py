"""T1.3 QoS runtime proofs (container only; needs rclpy).

Run inside d1-lyrical:
  /opt/venv/bin/python tests/test_qos_ros.py
Asserts txn_qos() builds BEST_EFFORT/VOLATILE/KEEP_LAST at the frozen
depth, and that TXN_CONTROL_TOPICS is exactly the five topics.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rclpy.qos import (DurabilityPolicy, HistoryPolicy,
                       ReliabilityPolicy)

from efrs_ros2 import msgspec as M
from efrs_ros2.rosutil import TXN_CONTROL_TOPICS, txn_qos


def test_txn_qos_runtime():
    assert set(TXN_CONTROL_TOPICS) == {"prepare", "vote", "abort",
                                       "commit", "ack"}
    for n in (3, 5, 20):
        q = txn_qos(M.control_depth(n))
        assert q.reliability == ReliabilityPolicy.BEST_EFFORT, q.reliability
        assert q.durability == DurabilityPolicy.VOLATILE, q.durability
        assert q.history == HistoryPolicy.KEEP_LAST, q.history
        assert q.depth == M.control_depth(n), q.depth
    assert txn_qos(48).depth == 48


if __name__ == "__main__":
    test_txn_qos_runtime()
    print("efrs QoS runtime proofs passed")
