"""One-shot admin/motion probe helpers (run inside the container)."""

import json
import sys
import time

import rclpy
from std_msgs.msg import String


def propose(epoch: int):
    rclpy.init()
    n = rclpy.create_node("probe_admin")
    p = n.create_publisher(String, "/efrs/admin", 10)
    m = String(data=json.dumps({"op": "propose", "epoch": epoch}))
    for _ in range(10):
        p.publish(m)
        time.sleep(0.1)
    n.destroy_node()
    rclpy.shutdown()
    print("PROPOSED", epoch)


def motion(robot: str, epoch: int, h: str, n_cmds: int = 3):
    rclpy.init()
    n = rclpy.create_node("probe_motion")
    p = n.create_publisher(String, "/efrs/motion_cmd", 10)
    for i in range(n_cmds):
        m = String(data=json.dumps(
            {"v": "efrs/1", "cmd_id": f"{robot}-{i}",
             "robot": robot, "required_epoch": epoch,
             "required_hash": h, "vx": 0.1, "vyaw": 0.0}))
        p.publish(m)
        time.sleep(0.2)
    n.destroy_node()
    rclpy.shutdown()
    print("MOTION-SENT", robot, epoch)


if __name__ == "__main__":
    if sys.argv[1] == "propose":
        propose(int(sys.argv[2]))
    elif sys.argv[1] == "motion":
        motion(sys.argv[2], int(sys.argv[3]), sys.argv[4])
