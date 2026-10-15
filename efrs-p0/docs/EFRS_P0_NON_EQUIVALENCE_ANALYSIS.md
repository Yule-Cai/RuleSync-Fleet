# EFRS-P0 Non-Equivalence Analysis (claim decomposition + B0–B4)

## 1. Candidate-claim decomposition

Candidate: "Epoch-fenced hard safety-rule execution in robot fleets,
with bounded obsolete-rule motion authorization and mandatory
reconciliation under network partition and restart."

A. Known mechanisms (each standard; T12 boundary doc disclaims all):
2PC prepare/vote/commit/abort shape; WAL crash recovery with fsync
linearization; session leases + renewal; fencing generations with
max-seen rejection at the effect boundary (Chubby sequencers;
Kleppmann fencing formulation); quorum-READY voting; retry with fresh
attempt identity; abort/timeout; dedup/idempotent re-application;
heartbeat contact; pull-based anti-entropy repair; motion gating as a
concept; RTA-style supervision + HOLD-as-recovery.

B. Robotics-specific adaptations (engineering, not mechanisms):
epoch+hash stamped per motion command and checked at the last
software boundary before release; hard rules as KEEP_OUT polygons
versioned by epoch; HOLD-as-safe-state with latched reason; B_real =
lease+guard+jitter budget decomposition; reconcile-before-motion
after restart/heal; Gazebo-validated egress behavior.

C. Potentially new protocol composition: reachable-unanimity 2PC +
WAL linearization + generation-scoped attempts + restart re-fence +
adopt-only-current contact-sync + pull reconciliation + conjunctive
per-command fence gate, for fleet rule-snapshot sync. (Tested §3.)

D. Potentially new formal property: bounded obsolete-rule motion
authorization under partition+restart with mandatory reconciliation
(I5 + B_real + I7). (Audited in THEOREM_AUDIT; preliminary only.)

E. Existing systems with equivalent behavior: B3 by construction
(§3); Chubby-style primitives for the fencing/lease halves; DAS 2026
disclosures for the actuator-finality half (single-platform);
Open-RMF lane closure for the application shape at zero guarantees;
RTA/Simplex for the supervision shape at zero distribution.

No composition is labeled novel without a non-equivalence argument —
none is found (§3).

## 2. Reference systems (conceptual; same lenses each)

Common lenses: commit semantics / partition model / motion-execution
boundary / restart model / timing assumptions / local state / safety
bound / conditional liveness.

B0 Plain 2PC: commit = all-participant READY, no durability stated;
partitions leave non-voters on old state with no expiry; motion
boundary ungated; restart may re-apply older COMMIT (rollback);
timing none. T0 exhibits: stale-rule window (S1/S6), I1 rollback
(S7), superseded post-restart (S8). Liveness: blocks on any
non-voter. ⇒ fails I1/I3/I5/I6/I7. (Executed, not hypothetical.)

B1 2PC + local lease expiry: adds per-robot lease on adopted state;
expiry ⇒ local hold. Closes UNBOUNDED staleness (I5-form) but NOT:
late-COMMIT rollback (I1), hash-divergence (I2), stale-command
execution while lease live (I3), restart-amnesia (I6), or
reconnect-without-reconcile (I7). Restart still lands actionable if
lease file persists. Liveness unchanged (still all-participant).
⇒ partial; T0 A3-class bug (renewal extends without adoption) lives
here if renewal is naive — the exact fault B1 does not exclude.

B2 B1 + actuation-side fencing: adds generation check at motion
release (reject lower-than-seen). Closes stale-coordinator /
superseded-generation actuation. Still missing: hash-bound adoption
(I2), reconcile-before-motion (I6/I7 as a rule — lease covers the
timing but a restarted robot with a live lease file acts immediately
on possibly-superseded state), adopt-only-current contact-sync (B1's
renewal bug survives unless renewal is currency-checked).
⇒ I1 (rollback of same-epoch-different-hash) still open without
content binding; I6/I7 open without reconcile discipline.

B3 B2 + epoch reconciliation + fail-safe HOLD: adds pull/catch-up to
current epoch with content verification, HOLD as default (motion
only when reconciled + live + current), adopt-only-current renewal.
With these parts, B3 reproduces: I1 (monotonic adopt + hash check +
idempotent same-epoch), I2 (hash-verified adoption), I3 (conjunctive
gate), I4 (lease ⇒ hold), I5 (no post-expiry execution + no
obsolete-currency renewal ⇒ bound = residual lease + margins),
I6/I7 (unreconciled ⇒ hold; heal authorizes nothing by itself).
Restart: durable state + re-fence + pull (standard WAL+fencing,
same as EFRS §G1-narrowed). Liveness under partition equals EFRS's
iff B3 adopts the same reachable-unanimity rule — a one-line
threshold choice using existing vote state, not a new mechanism.

B4 Existing supervisor/fleet-adapter + conventional versioned update
logic: e.g. RTA-style monitor with versioned rule sets + lease-bound
enforcement + reconnect re-sync + HOLD default, or Open-RMF lane
closure hardened with epochs/hashes/leases/reconcile. No off-shelf
integrated instance exists; conceptually it converges to B3. Its
relevance is evidentiary: EFRS's contribution over B4 is the ROS2
realization + measurement (ledgers, fault matrix, witnesses), not a
mechanism B4 cannot host.

## 3. The B3 question (NOT weakened: B3 gets everything its name says)

Can B3 reproduce every EFRS invariant without any new mechanism or
state? Expected answer: YES, for all of I1–I7, for these reasons:

- Every EFRS safety check consumes only state B3 already holds
  (epoch, content hash, lease deadline, fence generation, reconciled
  flag) or standard crash-recovery state (durable epoch, abort set).
- Generations/supersede/idempotent re-vote are liveness machinery
  (T1.1 repair, disclaimed generic); they change no safety verdict.
- Reachable-unanimity is a threshold parameterization of the vote
  rule, reproducible with B3's existing votes + presence state; the
  excluded-robot safety case (lease expiry) is already B3's I4.
- Restart re-fence + single replay + pull catch-up is textbook
  WAL + fencing (Chubby-pattern), reproducible with B3's fence +
  durable state.
- Contact-sync tightening (never-adopt-via-renew; newer⇒pull;
  obsolete⇒ignore) is a rule over existing (epoch, lease) state —
  the very rule whose absence is the A3 bug; a B3 that "includes
  epoch reconciliation" includes it by definition. (If a B3
  implementer writes naive renewal, they reproduce A3, not EFRS —
  but that is an implementation bug in B3, not a missing mechanism.)

Minimal-counterexample attempt (required): a trace where careful-B3
violates an EFRS invariant. None constructed. The T0 counterexample
suite targets plain-2PC/broadcast only; no B3-class system was ever
run or exhibited. The strongest near-miss (naive-renewal B3
reproduces A3) fails the test because currency-checked renewal is
part of what "epoch reconciliation" means. Falsifier accepted in
advance: exhibit such a trace and this section is refuted.

VERDICT: potential protocol equivalence on all safety invariants.
EFRS's distinctive content vs B3 is liveness engineering (explicitly
disclaimed generic) + ROS2 realization/measurement. Non-equivalence
is NOT established.
