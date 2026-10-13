# EFRS-T1.2 Preregistration — Eventual-Heal + Congestion-Safe Recovery Gate

Date: 2026-10-14. Frozen BEFORE any T1.2 implementation or experiment.
Parent closeouts: `efrs-t1/docs/EFRS_T1_RESEARCH_DECISION.md` (T1 verdict),
`efrs-t11/docs/EFRS_T11_FINAL_RESEARCH_DECISION.md` (T1.1 STOP +
adjudication). Liveness boundary: `efrs-t11/docs/EFRS_T11_LIVENESS_CONTRACT.md`
(still binding; §B of the authorization restates the claim).

## Frozen claims (§B)

SAFETY: under the modeled failures, obsolete rule authorization is
fenced within B_real = 1300 ms.
CONDITIONAL LIVENESS: if a healable fault execution reaches GST after
which all required participants are operational, mutually reachable,
and transaction messages are eventually delivered within the declared
bound, then a pending logical update eventually terminates and update
progress resumes.
BANNED: progress under permanent partition; non-blocking atomic commit
under arbitrary faults; consensus under asynchronous partitions;
retries-as-novel.

## Safety semantics (§C, unchanged)

I1..I7, B_real, epoch monotonicity, epoch/hash binding, MotionFence
semantics, lease expiry, contact-sync renewal (T1.1 tightened form),
reconciliation, txn_id (epoch,hash,generation), 1500 ms attempt
deadline, timeout ABORT, automatic new-generation re-attempt, WAL
commit linearization, unanimity / existing commit semantics.
FORBIDDEN: majority quorum, skipping unreachable robots, reachable-only
commits, lease extension, B_real change, deadline change, Raft/Paxos,
dynamic quorum, HOLD weakening.

## Protocol delta vs T1.1 (engineering amendment, §D)

T1.1's 10 Hz PREPARE retransmission and infinite COMMIT redrive are
SUPERSEDED (congestion amplification, T1.1 adjudication §4). Recovery
is by bounded-rate generation retry ONLY:

- D1 PREPARE: exactly ONE publication per attempt, at attempt start.
  No in-attempt republish. Incomplete at 1500 ms → ABORT → exactly one
  heartbeat period (100 ms) later a NEW generation with one new
  PREPARE. Recovery rate ≤ ~1 attempt / 1.6 s (derived, not tuned).
- D2 VOTE: at most ONE per robot per txn_id. Duplicate PREPARE(txn)
  is recognized idempotently and emits NOTHING further. A new
  generation's PREPARE may elicit one fresh VOTE.
- D3 COMMIT: exactly ONE publication per durable commit. No
  ACK-driven redrive. Missed-COMMIT catch-up runs ONLY through the
  existing paths: newer-epoch RENEW triggers reconcile-pull, the
  reconcile_rep installs authoritatively, lease expiry HOLDs while
  disconnected. Coordinator restart after a durable COMMIT allows ONE
  COMMIT replay (restart recovery, not a loop).
- D4 ACK: at most one per robot per txn_id. ACK is propagation
  evidence only, never a commit precondition.
- Unchanged: abort/reattempt/restart-disambiguation state machines,
  contact-sync tightening, `--old-renewal` A3 path, all thresholds.

## Queue sizing (§E, frozen formula)

`CONTROL_DEPTH = max(32, 2 * N_ROBOTS + 8)` (N=3→32, N=5→32, N=20→48).
Applies to publishers AND subscribers of PREPARE/VOTE/ABORT/COMMIT/ACK
only. Rationale (frozen): one burst holds ~N votes + N ACKs + margin.
Telemetry (renew/state/motion) stays at depth 10. Never retuned after
results. Pure-function tests pin the 3/5/20 mapping.

## Local safety ledger (§F, frozen schema)

Every MotionFence appends one JSONL record per authorization decision
to a LOCAL file (not via ROS/shim), flushed + fsync'd BEFORE an ACCEPT
is published. Required fields: monotonic_ns, robot_id,
local_committed_epoch, local_committed_hash, lease_deadline_monotonic_ns,
required_epoch, required_hash, cmd_id, decision (ACCEPT/REJECT),
reject_reason (nullable), reconciled (bool), holding (bool),
fence_seen (nullable; agent publishes its fence generation in state_msg
as an additive optional field). F1 audit (`ledger_audit.py`): every
ACCEPT must satisfy now ≤ lease_deadline, epoch+hash equality, and
reconciled-and-not-holding; accepted_after_expiry / mismatch / hash /
reconciling all 0; 100% ACCEPT coverage by ledger rows (joined by
cmd_id); missing/corrupt ledger ⇒ run evidence-incomplete (never PASS).

## Model plan (§G)

`efrs-t12/model/` from the T1.1 model, updated ONLY for: one-PREPARE /
one-VOTE / timeout-ABORT / new-generation retry / one-COMMIT /
reconcile catch-up / no ACK redrive. Re-run T0-9 + K1–K10 + renewal
cases. New schedules: first PREPARE lost; first VOTE lost; multiple
first votes lost; first COMMIT lost to one / several participants;
miss-COMMIT-then-newer-RENEW; miss-COMMIT-then-partition-to-expiry;
heal after 1 / 3 aborted generations; permanent loss (safety/HOLD
only, NO commit expectation); restart after durable COMMIT; duplicate
PREPARE/VOTE/COMMIT. Liveness monitor fires ONLY on EVENTUAL_HEAL
schedules. Mandatory: I1–I7 zero, 200 fuzz seeds zero EFRS violations.
TLC supplemental only.

## Workloads (§H, separation mandatory)

- W-SUSTAINED (`SCALE20_SUSTAINED_LOSS_SAFETY`): the EXACT frozen
  T1/T1.1 scale trace (cumulative loss_random unchanged, 265 s).
  Safety/stress ONLY: no commit-count requirement. Report commits,
  HOLD fraction, ledger accepts/rejects, accepted_after_expiry(=0),
  mismatch accepts(=0), stale duration(≤B_real), CPU/RSS, message
  counts. Progress may stop; safety must hold.
- W-HEAL (`SCALE20_EVENTUAL_HEAL_LIVENESS`): T1 fault ORDERING kept;
  every unterminated `loss_random` gets `until = t + 3000 ms`
  (frozen: exactly two 1500 ms windows); all other finite faults keep
  frozen durations. GST = end of the last fault; after GST no new
  loss/partition/crash fault is injected until the pending update
  commits (verified by construction script, output recorded).
  Sequential logical issue (§I): epochs 1..100, e+1 issued only after
  e durably COMMITTED (runner mode, no proposal queue); all waiting
  counts in wall clock; retries ≠ new updates. Duration cap 600 s.
- Recovery timeout (§J): 10 s inherited. Per healable update record
  T_GST/T_COMMIT/T_heal_to_commit; require max ≤ 10 s (max gates,
  percentiles reported).

## Deterministic 13/20 replay (§K, G2)

No timing parameters. Gen-scoped vote drop: exactly 7 fixed robots'
gen-0 VOTEs dropped (new shim match key `txn_gen`; gen-1+ traffic
structurally unimpaired — timing-independent heal-equivalence), all
participants alive/reachable throughout, one timed epoch-1 propose.
Require: g0 aborts (13/20) → generation increments → later generation
commits automatically (no manual re-propose) → no stale violation.
Replaces "natural replay must spontaneously yield 13/20".

## Regressions (folded T1.1 O/P, §§M–N; witness §Q held to the end)

- 3-robot F0–F15 (T1 fault defs), final EFRS, 30 reps/fault: zero
  I1–I7, zero accepted_after_expiry, zero B_real violations; healable
  cases recover ≤ 10 s. A3 old-renewal reproduces the known bug.
- 5-robot frozen schedules + I2 integrity (reject + HOLD/reconcile,
  no inconsistent authorization).
- Physical witness (blessed harness): 3/3 HOLD→reconcile→detour→resume
  on final EFRS only; T1 Plain2PC reused (no 2PC rerun, no retrofit).

## Gates (§R, ANY fail → STOP; no post-hoc tuning of any frozen value)

G1 model (I1–I7 zero + heal-schedules commit). G2 13/20 replay
(abort→new gen→commit). G3 W-HEAL 100/100. G4 every heal-to-commit
≤ 10 s. G5 W-SUSTAINED (accepted_after_expiry = mismatch = 0, stale
≤ B_real). G6 100% ledger coverage, zero unverifiable ACCEPT. G7
3-robot clean. G8 5-robot/I2 clean. G9 A3 reproduces/absent. G10
witness 3/3.

## Deliverables (§U)

`efrs-t12/reports/EFRS_T12_REPORT.md`,
`efrs-t12/reports/efrs_t12_results.json` (19 items verbatim).
Mechanical verdict EFRS_T12_PASS / EFRS_T12_FAIL only.
