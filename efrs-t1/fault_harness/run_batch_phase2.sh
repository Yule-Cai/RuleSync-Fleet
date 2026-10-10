#!/bin/bash
# Post-campaign phases (run AFTER t1_3robot_rep completes):
#  1. A1/A2/A3 ablation repros (already done 2026-10-10; skip if present)
#  2. 5-robot systematic (EFRS) + I2
#  3. 20-robot scale
#  4. aggregate everything -> gate verdict
# Sequential. Each step is idempotent-ish (skips existing records).
H=/home/gamer/RuleSync-Fleet/efrs-t1/fault_harness
E=/home/gamer/RuleSync-Fleet/efrs-t1/experiments
R=$H/run_one.sh
D5=/ws/efrs-t1/experiments/t1_5robot
DSCALE=/ws/efrs-t1/experiments/t1_20robot

echo "=== ablation repros (skip if rec exists) ==="
for a in A1 A2 A3; do
  if [ ! -f $E/t1_3robot/rec-efrs-$a.json ]; then
    echo "MISSING ablation $a (rerun manually)"
  fi
done

echo "=== 5-robot + I2 ==="
mkdir -p /home/gamer/RuleSync-Fleet/efrs-t1/experiments/t1_5robot
bash $H/run_batch_5robot.sh

echo "=== 20-robot scale ==="
python3 $H/scale_20robot.py --outdir $E/t1_20robot \
  --repo-mount /home/gamer/RuleSync-Fleet

echo "=== aggregate ==="
python3 $H/rep_aggregate.py --dir $E/t1_3robot_rep \
  --out $E/t1_3robot_rep_agg.json
echo PHASE2-DONE
