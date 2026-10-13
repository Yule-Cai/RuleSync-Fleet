# EFRS-T1 Research Decision (frozen negative result)

Date: 2026-10-12/13. Research-lead decision. This document freezes the
T1 verdict exactly as closed. T1 is NOT rewritten as a partial PASS.

## Frozen verdict

- SAFETY PASS
- LIVENESS FAIL
- T1 OVERALL FAIL → STOP (entered; T1.1 authorized separately)

## Frozen safety evidence (preserved, not re-argued)

- 3-robot deterministic matrix: 16/16 EFRS cells, zero contradictory
  (epoch_mismatch + invalid_lease + unreconciled = 0), zero rollbacks,
  stale_max ≤ 153.8 ms vs B_real = 1300 ms.
- 30x campaign (1440 runs, n=30/cell): EFRS max stale 181.3 ms,
  contradictory 0, rollbacks 0, all 16 faults.
- 5-robot systematic + combined schedules (11) + I2/I2B: stale ≤163.1
  ms, zero safety violations; integrity rejections correct.
- Ablations behave as positive controls: A1/A2 (fence/lease removed)
  accept stale authorizations; A3 reproduces the T0 renewal bug
  (7830.8 ms stale) while final EFRS does not.
- Baselines reproduce stale-window counterexamples (up to ~12.6 s;
  2PC F12: 90 rollbacks).
- Physical Gazebo witness (3x EFRS + 3x 2PC, amended harness
  5e2e8201…): partitioned R3 lease-HELD 112x, healed, reconciled,
  detoured, resumed; 2PC R3 drove stale straight through (40.4 s).
- B_real = 1300 ms unchanged throughout.

## Frozen liveness counterexample (T1 scale-20)

- 20 robots (1 coordinator + 20 agents + 20 fences), 100 logical
  updates proposed, **0 committed** (WAL empty).
- First prepare round: **13/20 votes** inside the single-shot 1500 ms
  window; no prepare retransmission; no timeout-abort/retry path.
- Coordinator wedged permanently in WAIT_VOTES; 99 subsequent proposes
  rejected silently; 0 ABORT/COMMIT lines in 265 s.
- Fail-safe behavior correct and preserved as evidence: **237
  lease-HOLD events**, **zero stale-motion violations** over 265 s of
  degraded operation (20% loss + partition groups ≤3 robots).
- A halted fleet with zero stale motion is correct fail-safe behavior,
  NOT protocol success. 100 proposals ≠ 100 committed updates.

## Decision chain (provenance)

- T1 freeze `fa9310e` (runner `59aeb6a42281`) → all deterministic
  evidence.
- Witness-only harness amendment `3c08041` (runner `5e2e8201…`,
  `efrs_ros2/` untouched) → witness evidence only.
- T1 final report `45b810f`: SAFETY PASS / LIVENESS FAIL / OVERALL FAIL.
- Scale disposition and T1.1 authorization: research-lead decisions
  2026-10-12/13. No deadlines lengthened, no quorum changed, no leases
  extended, no consensus added, no stalled updates hidden.

## What T1.1 may and may not do

- MAY: restore progress after transient communication failure/healing
  (eventual-heal liveness repair), with separate transaction attempt
  identity, idempotent retransmission, explicit timeout abort,
  automatic re-attempt, commit dissemination/ACK recovery, coordinator
  restart disambiguation.
- MAY NOT: change any safety semantic listed in the T1.1 authorization
  §C (epoch monotonicity, epoch/hash binding, MotionFence
  authorization, lease expiry, contact-sync renewal, reconciliation,
  I1..I7, B_real, commit-threshold semantics). Specifically: no
  majority quorum, no skipping unreachable robots, no lease extension
  for votes, no reachable-only commits, no MotionFence weakening, no
  B_real change, no stale-epoch renewal, no Raft/Paxos/consensus.
