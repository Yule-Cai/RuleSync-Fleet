# EFRS-P1 Mock Reviews (Phase D; independent; fatal vs fixable split)

## R1 — Distributed systems reviewer: novelty and B3 equivalence

Summary: fleet rule rollout with epoch/hash/lease/fence/reconcile;
evaluated in ROS 2 fault injection. Score: REJECT (weak-reject at
best). Confidence: high.

Strengths: honest baselines (plain 2PC exhibited failing); the
reachable-unanimity + contact-sync details are careful; amendments
disclosed rather than hidden.

FATAL W1 (novelty): The safety story is 2PC + leases + fencing +
reconciliation + HOLD. Each is textbook (Chubby sequencers for the
fence; session leases for currency; WAL for crash recovery; pull
repair for catch-up). The paper's own B3 construction concedes a
careful baseline reproduces every invariant. There is no new
mechanism, no new impossibility result, no new bound technique —
B_real is one lease cycle plus engineering margins, i.e. definitional.
A systems venue that requires architectural novelty should reject.

FATAL W2 (formal claims): The "theorem" is a small-instance model
check plus a conditional derivation. T-RO/NSDI-style reviewers will
read I5 as lease-expiry restated. Do not dress it as a result.

Fixable m1: The B3-first related-work posture is the right call —
keep it, sharpen it (add the falsifier criterion from P0 §6 so the
equivalence reads as a tested claim, not a shrug).
Fixable m2: Drop any lingering "protocol" language ("our protocol
guarantees") in favor of "our assembly enforces"; one careless verb
will sink the paper with this reviewer.
Fixable m3: Cite the 2026 DAS drafts before R1 finds them; delimit
single-platform vs fleet-commit scope in one paragraph.

R1's bar for flipping: a B3-breaking trace or a genuinely new
mechanism. Neither exists. At a systems-heavy venue R1 dissents; at
RA-L/RAM/ICRA-systems R1 is overruled only if evaluation depth
carries (R3's call).

## R2 — Robotics safety reviewer: physical guarantees, stopping, hardware

Summary: scored against safety claims for real robots. Score:
REJECT as safety paper; WEAK-ACCEPT-AS-SYSTEMS-EVALUATION if the
trichotomy is enforced ruthlessly. Confidence: high.

FATAL W1 (stopping/compliance gap): Bounded AUTHORIZATION is not
bounded STOPPING and neither is zone COMPLIANCE. The Gazebo witness
shows egress ≤3.1 s for one scenario — a measurement, not a bound —
and the 2PC 40.4 s contrast is a comparison, not a guarantee. Any
sentence a safety reviewer can read as "robots comply with new
keep-out zones within X" kills the paper. The outline's trichotomy
must be enforced in EVERY section, figure caption, and the abstract.

FATAL W2 (no hardware): lightweight processes on one host + Gazebo
physics. No actuator latency, no real network, no clock domain other
than the host's, no sensor in the loop. For a SAFETY venue this is
disqualifying; for a systems venue it bounds the claim (middleware
timing real, physics simulated — say exactly that).

Fixable m1: Epoch-gated metric discipline (already in Q: pre-commit
transit allowed, post-commit egress measured) must be visibly
correct in every plot — R2 will recheck denominators.
Fixable m2: Move guard/jitter budgets (50/250 ms) from background to
a stated-assumption box with "unstressed" labeled; R2 respects
declared assumptions, punishes buried ones.
Fixable m3: HOLD-as-safe-state needs the turtlebot-stop analysis
(one paragraph: what HOLD commands physically, measured stop
behavior in Gazebo) or R2 calls it a software flag, not safety.

R2's bar for flipping: hardware trials with measured stop behavior
and zone-egress distributions. Not available in existing evidence;
would be NEW experiments (lead authorization required).

## R3 — Applied robotics systems reviewer: relevance, reproducibility, completeness

Summary: judged as a working-systems + evaluation contribution.
Score: WEAK ACCEPT (borderline). Confidence: medium.

Strengths (carrying the paper): rare combination of preregistered
fault battery + per-decision audit ledgers + retained negatives +
positive controls that actually break (A1/A2/A3) + validity-ledger
practice + full amendment provenance. The 480-run matrix with
ledger-joined ACCEPTs, the W-HEAL 100/100 under healed workload, and
the published wedge anatomy are exactly the artifacts systems
reviewers wish more papers had. Reproducibility posture is strong
(frozen schedules, deterministic shim, dual-freeze chain).

W1 (serious, not quite fatal): single-host + Gazebo-only validation
caps the systems claim at "middleware-real, physics-simulated." At
RA-L/ICRA this is common and survivable; at JFR it is excluded by
rule (their validation policy bars simulation/lab-only work — do not
submit there). Completeness gap: B3/B4 never implemented, so the
evaluation compares against deliberately weak baselines (plain 2PC,
broadcast) — R3 discounts "beats 2PC" heavily; the paper must lean
on absolute-envelope + controls + negatives, never on baseline gaps.

Fixable m1: artifact appendix (schedules, ledger schema, analysis
scripts versions) — RAM R-articles / RA-L multimedia welcome it.
Fixable m2: cost the evaluation (node counts, host specs, runtimes)
so readers can reproduce the battery.
Fixable m3: one table mapping every P0 unsupported-claim to its
absence from the paper ("we do not claim X") — turns R1/R2's
ammunition into diligence signals.

R3's bar for accept: B3-honest framing + trichotomy discipline +
artifact completeness. All achievable in writing. R3's reject
trigger: any Novel-Protocol or immediate-compliance sentence, or a
JFR-style venue mismatch.

## Cross-review verdict

No fatal flaw is fixable by rewording alone EXCEPT through venue
choice: R1-fatal (novelty) and R2-fatal (safety/hardware) are
venue-relative; both are survived at RA-L / RAM / ICRA-systems IF
the paper is framed as design + measurement + lessons (C1–C3) with
the trichotomy enforced. JFR/Field-Robotics are hard-excluded by
their validation rules; T-RO by its bar. Residual risk even at fit
venues: an R1-strong panel rejects on B3-equivalence — estimated the
dominant failure mode, mitigated only by evaluation depth (R3's
strengths) and the B3-first related work.
