#!/bin/bash
# Launch one full EFRS stack (coordinator + agents + fences) in background.
# Args: PROTOCOL ROBOTS_CSV WALDIR RUN_SECONDS
PROTO="$1"; ROBOTS="$2"; WDIR="$3"; RUNSEC="$4"
source /opt/ros/lyrical/setup.bash
export PYTHONPATH="/ws/efrs-t1:${PYTHONPATH}"
mkdir -p "$WDIR"
/opt/venv/bin/python efrs_ros2/coordinator/coordinator.py \
  --protocol "$PROTO" --robots "$ROBOTS" --wal "$WDIR/wal.jsonl" \
  > "$WDIR/co.log" 2>&1 &
sleep 2
IFS=',' read -ra RS <<< "$ROBOTS"
for r in "${RS[@]}"; do
  /opt/venv/bin/python efrs_ros2/robot_agent/robot_agent.py \
    --robot "$r" --protocol "$PROTO" \
    --state-file "$WDIR/state-$r.json" > "$WDIR/agent-$r.log" 2>&1 &
  /opt/venv/bin/python efrs_ros2/motion_fence/motion_fence.py \
    --robot "$r" --protocol "$PROTO" > "$WDIR/fence-$r.log" 2>&1 &
done
sleep "$RUNSEC"
echo STACK-DONE
