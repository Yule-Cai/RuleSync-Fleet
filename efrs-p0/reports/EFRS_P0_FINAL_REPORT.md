# EFRS-P0 Final Report — Protocol Novelty & Paper Viability Audit

Read-only round. No code, schedule, report, parameter, or invariant
touched. No experiment run. No publication decision made here.
Artifacts: `efrs-p0/docs/` (5) + this report. HEAD verified
`5b7b1e8`, tracked tree clean at start.

## 1. Literature audit with links

Claim-level matrix: `docs/EFRS_P0_PRIOR_ART_MATRIX.md` (10 works +
internal base, each with problem/assumptions/mechanism/property/
epochs-fencing/actuation/partition-restart/limits/overlap/difference
and verified URLs). Headline: Chubby sequencers + session leases
(OSDI 2006) supply the fencing/lease primitives; Reitblatt (SIGCOMM
2012) + Mizrahi timed updates (SOSR 2015) supply the versioned-update
shape under NON-partition assumptions; RTA/Simplex/ASTM F3269 supply
the supervision shape for single systems; Open-RMF lane closures
supply the application shape at zero guarantees; SROS2/DDS supplies
static command authorization; geofence monitoring supplies single-
vehicle containment. None combines fleet rule versioning + lease/
fence motion gating + bounded staleness + reconciliation — but §5
shows the combination reduces to B3.

## 2. Comparison to 2026 execution-finality disclosures

Both mandatory drafts EXIST as individual Informational I-Ds (author
S. Das; unreviewed; not WG-adopted; no formal standing — recorded as
disclosures, not standards): (i) `draft-das-drip-uas-act-finality`
(-01 2026-09-18; -02 2026-10-13): per-act execution finality at a
Finality Sink, monotonic authority epochs, protected motion-admission
gate for road vehicles, composite multi-aircraft acts with HOLD safe
state, bounded offline operation; (ii) `draft-das-actuation-bound-
execution-finality` (-00 2026-09-15): actuation-bound invariant
(exact command + actuator + current authority/state + freshness +
non-bypassable path), prevention profile, formal model with
generation currency. Related: `draft-das-execution-handle` (-02,
handles/verify/consume/receipts) and `draft-das-ot-actuation-
finality` (-00 2026-08-27, policy epochs, sink-bound consumed
authority). Collision assessment: the actuator-finality HALF of the
EFRS claim (epoch-checked gate at the motion boundary, HOLD, bounded
offline operation, monotonic epochs) is now independently disclosed
in dated public documents — for single platforms, without fleet
commit semantics. A method paper's gate-half novelty faces these
disclosures regardless of their review status; the fleet-commit half
is not in them (but see §5: it reduces to B3). Status verified
2026-10-15 via datatracker.ietf.org.

## 3. Actual EFRS state machine

Full reconstruction: `docs/EFRS_P0_PROTOCOL_RECONSTRUCTION.md`.
Coordinator: propose→PREPARE(one/attempt)→reachable-unanimity decide→
WAL-commit-then-publish; timeout/reject aborts; gen-scoped re-attempts;
fence+1 + single replay + pending rebuild on restart. Agent: prepare/
commit/renew/reconcile with idempotent txn identity, supersede,
adopt-only-current contact-sync, restart-UNRECONCILED. MotionFence:
conjunctive per-command gate (epoch+hash+lease+reconciled+¬holding)
with fsync'd per-decision ledger. Commit rule is unanimity over the
OBSERVED REACHABLE SET (2 s window), NOT all-configured unanimity —
excluded-robot safety rides entirely on lease expiry.

## 4. Formal/implementation assumption gaps

Six recorded gaps (RECONSTRUCTION §12): (G1) T0 "re-fence through a
quorum" unimplemented — single coordinator, local fence+1 (harmless
narrowing); (G2) "quorum READY" formal vs reachable-unanimity code —
commit does not imply all-adopted; reconciliation lazy/pull
(behavioral fact, pro-B3); (G3) tick-bound vs B_real ms-budgets —
guard/jitter allocations measured-consistent, unstressed;
(G4) ablation escape-hatches in production code (documented
controls); (G5) single-host clocks — cross-machine untested, safety
needs local-monotonicity only; (G6) 1500 ms/2000 ms timing choices
are liveness-only.

## 5. Strong composite-baseline analysis

B0–B4 constructed over identical lenses in
`docs/EFRS_P0_NON_EQUIVALENCE_ANALYSIS.md`. B0 fails I1/I3/I5/I6/I7
(executed). B1 closes unbounded staleness only. B2 still open on
I1-content/I6/I7-discipline. B3 (2PC + lease + fencing + epoch
reconciliation + fail-safe HOLD) reproduces every EFRS safety
invariant with no new mechanism or state: checks consume held state;
generations are liveness machinery; reachable-unanimity is a
threshold parameterization; re-fence/replay/pull is textbook WAL +
fencing; contact-sync tightening is a rule over held state. B4
converges to B3 conceptually; its relevance is evidentiary.

## 6. Minimal non-equivalence witness or equivalence argument

Witness attempt REQUIRED and made: no trace constructed in which a
careful B3 violates an EFRS invariant (T0 suite targets plain-2PC/
broadcast only; B3 never run). Near-miss (naive-renewal B3 ≈ A3)
fails the test because currency-checked renewal is part of "epoch
reconciliation" by definition. Recorded: POTENTIAL PROTOCOL
EQUIVALENCE on all safety invariants; EFRS's distinctive content vs
B3 is disclaimed-generic liveness engineering + ROS2 realization/
measurement. Refutation criterion stated (exhibit such a trace).

## 7. Theorem status

`docs/EFRS_P0_THEOREM_AUDIT.md`: time points fixed (T_c WAL-append …
T_k reconcile); bound T_s ≤ T_c + B_real derived under explicit
A1–A8 (monotonic clocks, ≤50 ms fence scheduling, ≤250 ms drain,
honest coordinator, durable-state integrity, code-path restart, no
bypass, fence-on-path) with removal counterexamples (clock-jump ⇒
refuted; starvation ⇒ open; equivocation ⇒ outside model). Five-way
split recorded, including the explicit bar: bounded stale
authorization does NOT imply immediate physical zone compliance.
Statuses: everything CONDITIONAL and/or MODEL-CHECKED-ONLY (small
instance) and/or EMPIRICAL-ONLY. NO theorem tagged PROVEN. Nothing
REFUTED inside stated assumptions.

## 8. Existing evidence mapping

`docs/EFRS_P0_PAPER_CLAIM_MATRIX.md`: every frozen result mapped to
exactly the claim it supports (counterexample exhibition, bounded-
instance elimination, B_real margins ≥2.3x, load-bearing controls,
fail-safe demonstration, heal-liveness, restart, integrity, physical
behavior, frozen negative results); seven unsupported-claim classes
listed (unbounded proof, multi-machine clocks, scalability,
transport, immediate compliance, B3 comparison, beyond-I2B
adversarial). SCOPE check: T12 novelty file mixes SCOPE sensor-
corruption claims — flagged, quarantined, absent from P0 docs.
Amendment hygiene supports G4 (FAILs retained, ledger labeling,
diff-audited amendments, disclosed order deviation).

## 9. Novelty-risk assessment

Highest risks, ranked: (1) B3-equivalence — a competent reviewer
builds B3 in analysis and finds no residue (§6); (2) 2026 DAS
disclosures cover the gate-half with dated priority and formal
models (§2); (3) the bound is near-definitional given leases, so the
formal contribution reads as engineering hygiene, not a theorem
(§7); (4) T0 theorem self-limits to preliminary/bounded, citable by
reviewers against any stronger claim; (5) SCOPE contamination must be
policed in any future write-up (§8). Mitigating factors: genuine
ROS2 realization + measurement depth; disclosed-amendment
credibility; reachable-unanimity + contact-sync as careful (if
reproducible) design.

## 10. G1–G5

- G1 Problem distinctiveness: PARTIAL. Fleet rule-snapshot sync under
  partition is a genuine composition, but each half is established
  (fencing/leases; versioned updates; supervision) and the 2026
  drafts now disclose the actuator half.
- G2 Protocol non-equivalence: UNSUPPORTED. No mechanism/invariant
  resists careful-B3 reproduction (§6).
- G3 Formal contribution: PARTIAL. Bounded property under explicit
  assumptions + small-instance machine checking; no general proof;
  bound near-definitional.
- G4 System evidence: SUPPORTED. ROS2/Gazebo + fault-injection
  evidence is deep and amendments are disclosed, not concealed
  (validity ledger, retained FAILs).
- G5 Prior-art defensibility: PARTIAL. Survives as engineered system
  against adjacent methods; the METHOD claim does not survive B3 +
  DAS comparison.

## 11. Recommended classification

**SYSTEMS_PAPER_CANDIDATE** — EFRS is a meaningful engineered
robotics safety system with strong experimental evidence, but
algorithmic/protocol novelty is limited (B3-equivalence unrefuted;
gate-half independently disclosed; theorems conditional). Boundary
condition stated plainly: a venue/lead requiring method novelty
should read this as METHOD_NOVELTY_WEAK instead; no UNRESOLVED
blocker (no hidden collision, no theoretical uncertainty beyond the
recorded conditionality) and no NOVEL_PROTOCOL case (G2 fails). No
new-algorithm proposal is made (none authorized).

## 12. Exact remaining work, only if justified

Only under a SYSTEMS-track decision by the lead: (a) scoping note
quarantining SCOPE content out of any EFRS write-up; (b) B3 write-up
as the explicit related-work baseline (strongest-defense posture);
(c) DAS-draft citation with status + single-platform/fleet-commit
delimitation; (d) assumption table (A1–A8) printed in the paper, not
buried; (e) no new experiments needed for the classification itself.
If the lead requires method novelty instead: no recommended work —
the negative result stands, STOP.
