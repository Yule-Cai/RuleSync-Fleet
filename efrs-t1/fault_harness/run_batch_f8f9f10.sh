#!/bin/bash
R=/home/gamer/RuleSync-Fleet/efrs-t1/fault_harness/run_one.sh
for f in F8 F9 F10; do
  for p in broadcast 2pc efrs; do
    rm -rf /home/gamer/RuleSync-Fleet/efrs-t1/experiments/t1_3robot/rec-$p-$f-det*
    bash $R $p $f 205 det
  done
done
echo REDO3-DONE
