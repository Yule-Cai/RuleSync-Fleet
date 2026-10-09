#!/bin/bash
# Single scenario run helper (explicit paths, no loop variables).
# Args: PROTO FAULT DOMAIN TAG SCHEDDIR OUTDIR
set -e
PROTO="$1"; FAULT="$2"; DOMAIN="$3"; TAG="$4"
SCHEDDIR="$5"; OUTDIR="$6"
mkdir -p "$OUTDIR"
podman run --rm --shm-size=2g -v /home/gamer/RuleSync-Fleet:/ws \
  -w /ws/efrs-t1 -e ROS_DOMAIN_ID="$DOMAIN" d1-lyrical bash -lc \
  "source /opt/ros/lyrical/setup.bash && /opt/venv/bin/python \
  fault_harness/runner.py \
  --schedule $SCHEDDIR/sched-${PROTO}-${FAULT}.json \
  --out $OUTDIR/rec-${PROTO}-${FAULT}-${TAG}.json \
  --domain-id ${DOMAIN} --repo /ws/efrs-t1 --python /opt/venv/bin/python"
