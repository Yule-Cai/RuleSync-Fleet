#!/bin/bash
# F0 regression x 3 protocols (payload-hash code validation).
R=/home/gamer/RuleSync-Fleet/efrs-t1/fault_harness/run_one.sh
bash $R broadcast F0 201 F0r
bash $R 2pc F0 202 F0r
bash $R efrs F0 203 F0r
echo F0-REG-DONE
