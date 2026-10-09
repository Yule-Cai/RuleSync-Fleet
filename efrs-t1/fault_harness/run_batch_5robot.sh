#!/bin/bash
# Phase H (5-robot systematic, EFRS) + Phase I (I2 integrity).
# Sequential. Run AFTER the 30x campaign completes.
H=/home/gamer/RuleSync-Fleet/efrs-t1/fault_harness
R=$H/run_one.sh
D=/ws/efrs-t1/experiments/t1_5robot
python3 $H/gen_5robot.py /home/gamer/RuleSync-Fleet/efrs-t1/experiments/t1_5robot
DOM=150
for s in P41 P32 PCOORD P2ISO C_PLUS_LATE C_PART_RESTART C_COORD_ROBOT C_LOSS_REORDER C_STALE_RECONNECT I2; do
  bash $R efrs $s $DOM $s $D $D
  DOM=$((DOM + 1))
done
echo PHASE-HI-DONE
