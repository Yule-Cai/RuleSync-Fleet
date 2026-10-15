# EFRS-P1 Contribution Matrix (Phase A; B3-honest)

Rule: at most three contributions. Each must remain meaningful even if
a careful baseline combines 2PC + lease + epoch fencing +
reconciliation + fail-safe HOLD. No superiority over B3 is claimed
(B3 was never implemented or evaluated). If a contribution is merely
"these mechanisms can be combined in ROS 2", it is labeled exactly
that. P0 verdicts stand (G2 unsupported; no mechanism novelty).

## C1. A lease-and-fence enforcement stack for ROS 2 fleet rule
rollout, built, measured, and auditable
Classes: robotics-specific system design + implementation and
reproducibility. (NOT novel scientific knowledge.)
Content: epoch+hash-tagged hard-rule snapshots; reachable-unanimity
2PC with generation-scoped attempts and WAL linearization; per-command
conjunctive motion gate at the last software boundary (epoch, hash,
live lease, reconciled, not-holding); adopt-only-current contact
sync; pull reconciliation; HOLD-as-default; per-decision fsync'd
audit ledgers joined against every ACCEPT. What survives B3: the
existence proof that this stack can be assembled inside real ROS 2 /
DDS middleware with all timing real (discovery storms, DDS loss,
steady-clock leases) and every authorization decision third-party-
auditable from local ledgers. Explicitly: the contribution is that
the combination was built and measured in ROS 2 — not that the
combination is new.

## C2. Preregistered fault-injection methodology with retained
negative results and a validity-ledger discipline
Classes: engineering lessons from failures + implementation and
reproducibility. (NOT novel scientific knowledge.)
Content: frozen fault schedules with dual-freeze provenance; an
evidence-validity ledger that voids liveness readings while keeping
safety readings (loss_random.until finding); the T1 scale-20 wedge
anatomy (13/20 votes, silent propose-rejection, 237 correct HOLDs)
published as formal negative evidence; workload-semantics vs
transport-hypothesis downgrade with the causal pair voided rather
than spun; A1/A2/A3 positive controls including a repaired control
(168 ms → 7792 ms). What survives B3: methodology and failure
knowledge are implementation-independent; a B3 paper would need the
same discipline, and this work exhibits it with all FAILs retained.

## C3. Measured bounded-stale-motion-authorization envelope with the
authorization / stopping / compliance trichotomy
Classes: robotics-specific system design (framing) + engineering
measurement. (NOT novel scientific knowledge; framing, not mechanism.)
Content: B_real = lease(1000) + guard(50) + jitter(250) decomposition
with measured margins (matrix 181 ms, W-HEAL 263 ms, M cell-max
552 ms, all inside 1300 ms); positive controls proving the metric
fires when mechanisms are removed; Gazebo witnesses showing the
residual that authorization bounds do NOT cover (inside-at-commit
egress ≤3.1 s vs 2PC 40.4 s straight-through). The trichotomy —
bounded stale-motion AUTHORIZATION vs physical motion STOPPING vs
actual COMPLIANCE with newly activated constraints — is a conceptual
clarification future fleet-safety work can reuse; no immediate-
compliance claim is made anywhere. What survives B3: the measured
envelope and the trichotomy are statements about the problem, not
about whose mechanism achieves them.

## Explicitly NOT contributions

- No new distributed protocol (B3-equivalence unrefuted, P0 §6).
- No new fencing/lease/consensus mechanism (all disclaimed, P0 §A).
- No formal theorem beyond conditional/bounded claims (P0 §7).
- No scalability result (scale story is failure→repair, not scaling).
- No transport finding (hypothesis downgraded; micro pair voided).
- No hardware validation (lightweight ROS 2 processes + Gazebo only).
