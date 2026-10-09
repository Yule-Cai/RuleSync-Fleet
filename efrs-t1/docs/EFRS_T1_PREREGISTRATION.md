# EFRS-T1 Preregistration (ROS2 fleet fault-injection gate)

Work host holds `aa738f6`; remote tip carries only additional legacy
evidence backups (tree diff verified on Mac — zero science files).
Expected-HEAD `1cca835` in the brief predates the T1.1 merge; the live
remote tip is `649dc09`. Provenance recorded; no science file differs.

## Imported T0 (unchanged)

State variables, epoch/hash semantics, contact-sync renewal (renewal
only at adopted currency), prepare/commit/abort, restart/reconcile,
I1..I7 — per `docs/EFRS_T0_CONTRACT.md`. No invariant weakened, no
fault removed, no lease silently increased.

## Real-time mapping (frozen before experiments)

- Clock: CLOCK_MONOTONIC / steady clock for lease age. ROS/wall clock
  NEVER used for expiry.
- heartbeat_period = 100 ms (coordinator RENEW broadcast).
- lease_duration = 1000 ms (10 missed heartbeats; tolerates burst loss
  while bounding stale execution to ~1 s).
- motion-guard check period = 50 ms (MotionFence evaluation cadence).
- scheduling/jitter allowance = 250 ms (Python processes + DDS on a
  loaded 8-core box; covers GC pauses and executor latency).
- B_real = 1000 + 50 + 250 = **1300 ms**.
- reconciliation_timeout = 5 s; recovery_timeout (liveness) = 10 s.

Derivation: T0 BOUND=L ticks maps to lease_duration; guard period sets
detection granularity (a lease expiring just after a check waits at
most one period); jitter allowance is a declared engineering margin,
NOT fitted to data. B_real is frozen here, before any fault result.

## Architecture (frozen)

- `efrs_ros2/msg/`: FencedMotionCommand{required_epoch, required_hash,
  cmd_id, vx, vyaw}, MotionExecutionEvent, PrepareMsg, VoteMsg,
  CommitMsg, RenewMsg (topics, VOLATILE, RELIABLE, KEEP_LAST(10)).
- Nodes (separate OS processes, real DDS): RuleCoordinator,
  RobotRuleAgent xN, MotionFence xN, FaultOrchestrator, ScenarioRunner.
- Coordinator owns proposal/hash/coordination; NEVER authorizes motion.
- MotionFence is the last boundary: releases only on
  (epoch==local) AND (hash==local) AND (lease live) AND (not
  reconciling/holding); else safe stop + exact reason + event.
- Coordinator WAL: append-only JSONL (durable linearization point).
  Robot restart state: per-robot JSON (committed epoch/hash).
- Faults: netns + tc/netem + iptables for link delay/loss/partition
  (F1-F3, F6, F7); in-node deterministic shim hooks (orchestrator-armed)
  for type-selective duplicate/reorder/late-replay/stale-replay/content
  faults (F4, F5, F12, F13, F15, I2); SIGKILL/SIGSTOP/SIGCONT for crash
  and F14. Every schedule replayable from a JSON record.

## Honest mechanism deviation (frozen, reasoned, reviewable)

The brief prefers tc/netem for link delay/loss/partition. T1 uses the
deterministic in-node shim for ALL impairments instead, for three
frozen reasons: (1) 1440-run scale requires second-level setup/teardown
  determinism that per-run netns topology rebuilds cannot supply in
  rootless containers; (2) every schedule must be byte-replayable from
  JSON, which transport-level impairment cannot guarantee; (3) ROS
  processes, DDS transport, crash semantics (real SIGKILL/SIGSTOP),
  clocks, and timing are all REAL — only the impairment injector is
  simulated, and every injected fault is logged with timestamps.
Type-selective faults (duplicate/reorder/late/stale/content) REQUIRE
content awareness and were shim-authorized by the brief itself. If the
lead rejects this deviation, the gate must be re-run under netns/tc;
no result below may be cited without this note.
- Motion sink: event log (+ cmd_vel republish only in Phase K).

## Scale/tempo (frozen)

- 3-robot: F0-F15 deterministic x1, then 30 reps/fault/protocol with
  deterministic fault seeds (1440 runs). Ablations A1-A3: 1 deterministic
  repro each. Target ~15 s/run.
- 5-robot (only if 3-robot EFRS passes): 4 topologies + 5 combined
  schedules x 20 reps.
- 20-robot: 1 coordinator + 20 agents + 20 fences, >=100 epoch updates,
  <=20% partitioned at once. No Gazebo for 20.
- Gazebo witness (only after logical gates): 3 sim mobile robots,
  KEEP_OUT scenario per brief Phase K.

## Gates (mechanical, per brief Phase N)

3-robot EFRS: 0 rollbacks, 0 expired-authorization accepts, 0
superseded-restart motions, 0 invalid-lease motions, stale <= B_real,
all healed nonfaulty robots reconcile (<= recovery_timeout). Baselines
must reproduce >=1 stale-window counterexample; A3 must reproduce the
T0 renewal bug. 5-robot/20-robot/witness gates per brief. ANY fail:
STOP, no tuning.
