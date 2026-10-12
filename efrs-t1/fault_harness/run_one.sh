#!/bin/bash
# Single scenario run helper (explicit paths, no loop variables).
# Args: PROTO FAULT DOMAIN TAG SCHEDDIR OUTDIR
set -e
PROTO="$1"; FAULT="$2"; DOMAIN="$3"; TAG="$4"
SCHEDDIR="$5"; OUTDIR="$6"
# NOTE: no mkdir here (container paths); the runner creates out dirs.
# Pre-run sweep: kill our leftover stack processes/containers so each
# run starts clean (crashed runs can orphan Gazebo-free node procs).
pkill -f "efrs_ros2/coordinator/coordinator.py" 2>/dev/null || true
pkill -f "efrs_ros2/robot_agent/robot_agent.py" 2>/dev/null || true
pkill -f "efrs_ros2/motion_fence/motion_fence.py" 2>/dev/null || true
podman rm -f $(podman ps --filter "ancestor=d1-lyrical" --format "{{.ID}}" 2>/dev/null) 2>/dev/null || true
sleep 2
podman run --rm --shm-size=2g -v /home/gamer/RuleSync-Fleet:/ws \
  -w /ws/efrs-t1 -e ROS_DOMAIN_ID="$DOMAIN" d1-lyrical bash -lc \
  "source /opt/ros/lyrical/setup.bash && /opt/venv/bin/python \
  fault_harness/runner.py \
  --schedule $SCHEDDIR/sched-${PROTO}-${FAULT}.json \
  --out $OUTDIR/rec-${PROTO}-${FAULT}-${TAG}.json \
  --domain-id ${DOMAIN} --repo /ws/efrs-t1 --python /opt/venv/bin/python"
