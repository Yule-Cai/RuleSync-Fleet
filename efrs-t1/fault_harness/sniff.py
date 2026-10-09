"""Sniff motion events for N seconds and print verdicts."""

import json
import sys
import time

import rclpy
from std_msgs.msg import String


def main() -> None:
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    rclpy.init()
    n = rclpy.create_node("sniff")
    evs = []
    n.create_subscription(String, "/efrs/motion_event",
                          lambda m: evs.append(json.loads(m.data)), 10)
    t0 = time.time()
    while time.time() - t0 < secs:
        rclpy.spin_once(n, timeout_sec=0.5)
    n.destroy_node()
    rclpy.shutdown()
    for e in evs:
        print(e["robot"], e["cmd_id"], e["required_epoch"], e["verdict"],
              e["reason"])


if __name__ == "__main__":
    main()
