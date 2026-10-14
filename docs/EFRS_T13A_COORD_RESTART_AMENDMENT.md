# EFRS-T1.3a Coordinator-Restart Amendment (surgical, lead-authorized)

Date: 2026-10-14/15. Research-lead decision: APPROVE SURGICAL
COORDINATOR-RESTART FIX. N mechanical FAIL remains historical; no
broad rerun authorized. This amends ONLY the restart replay ordering;
production protocol semantics otherwise untouched.

## Defect (frozen)

- C_COORD_ROBOT (T1.3a): committed epochs `[1]` (epoch 2 never
  attempted). Historical T1 result on the identical sched: `[1, 2]`.
- Coordinator crash (restart with durable WAL): `UnboundLocalError:
  cannot access local variable 'pub' where it is not associated with
  a value` at `coordinator.py` line 145 (`pub("commit", ...)` in the
  restart COMMIT-replay block). The restarted coordinator died on boot
  (10-line log: 2 restart lines + traceback); all post-restart epochs
  stalled. Preserved traceback (from
  `t13a_5robot/rec-efrs-C_COORD_ROBOT-C_COORD_ROBOT_procs/coordinator.log`):

      File ".../efrs_ros2/coordinator/coordinator.py", line 406, in <module>
          main()
      File ".../efrs_ros2/coordinator/coordinator.py", line 145, in main
          pub("commit", M.commit_msg(
      UnboundLocalError: cannot access local variable 'pub' (...)

- Root cause: the ONE-COMMIT restart replay block runs inline during
  WAL recovery, BEFORE the local helpers `pub()` and `snap_hash()`
  are defined (both are `def`s later in `main()`; the recovery code
  executes first, so the names are unbound).
- Additional issue (lead-noted): `snap_hash()` is likewise defined
  later and used by the replay block.
- Blast radius (verified): restart-with-durable-commit ONLY.
  Production MotionFence semantics unaffected. All other N cases
  (8 full commits + 2 T1-consistent non-commitments) untouched.
  Matrix (no coordinator restarts), W-HEAL (agent restarts only),
  K13 (no restarts) unaffected.

## Repair (this amendment)

- During WAL recovery: determine `replay_epoch` (= recovered durable
  epoch if > 0 else 0). All existing WAL/state recovery operations
  preserved verbatim (fence bump, logs, pending rebuild, aborted-gen
  retention, reject-terminal rebuild).
- AFTER both `snap_hash()` and `pub()` definitions: publish the
  single recovered COMMIT iff `replay_epoch > 0` (identical message
  contents: same txn/epoch/hash/fence/lease/rules as before).
- No change to: txn_id semantics, epoch/hash/fence values, commit
  quorum, WAL writes, lease, B_real, deadline/retry, DDS QoS,
  publisher depth, restart semantics, agent, fence, fault schedules.

## Tests (new, green pre-execution)

A. Empty WAL → coordinator starts without replay (AST: replay
   guarded by `replay_epoch > 0`; model K-behavior unchanged).
B. Nonempty WAL → no UnboundLocalError/NameError (AST: replay site
   textually follows both `def snap_hash` and `def pub`; container
   test boots coordinator paths... see below).
C. Exactly ONE recovered COMMIT (AST: single replay site; no loop;
   source-contract `pub("commit")` count unchanged at 3).
D. Metadata frozen (AST: replay builds txn/epoch/hash/fence from
   the same expressions as before the move).
E. Pending e+1 not auto-committed (unchanged guard: replay only
   republishes the durable epoch; `propose` monotonicity intact).
F. Replay-after-init + no redrive (AST: replay block positioned after
   helper defs; heartbeat contains no COMMIT publish).
- Executed: `tests/test_pure.py` (all green, incl. 2 new AST proofs)
  locally + in the frozen container pre-commit.

## Freeze / execution (per decision §§4–5)

- Amendment freeze commit (BEFORE execution): recorded below.
- Exactly ONE corrected C_COORD_ROBOT + F8/F9 diagnostics once each,
  frozen scheds, no other reruns.
