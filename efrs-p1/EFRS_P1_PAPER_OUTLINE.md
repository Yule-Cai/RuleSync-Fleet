# EFRS-P1 Paper Outline (Phase B; neutral title as proposed)

Title: "Epoch-Fenced Safety Rule Enforcement in ROS 2 Robot Fleets:
Design, Fault Injection, and Recovery"

## Abstract (draft, ~180 words)

Fleet-wide safety-rule changes (e.g. new keep-out zones) reach robots
at different times under partitions, crashes, and loss; a robot that
misses the update can keep executing obsolete rules without bound —
we exhibit this stale-rule window against broadcast and plain 2PC in
both a checker and ROS 2. This paper presents the design, fault-
injection evaluation, and recovery behavior of a ROS 2 enforcement
stack combining versioned rule snapshots (epoch + content hash),
lease-bound rule currency, fencing-generation checks, per-command
motion authorization at the last software boundary, and mandatory
reconciliation before motion resumes. The mechanisms are established;
the contribution is the B3-honest assembly C1, its measurement
against a frozen fault battery (480-run matrix, 5-robot injection,
20-robot eventual-heal 100/100, per-decision audit ledgers, Gazebo
witnesses), the retained negative results (scale-20 liveness failure
and its repair path), and the authorization/stopping/compliance
trichotomy. Bounded stale-motion authorization (≤1300 ms budget,
measured ≤552 ms worst cell) is distinguished throughout from
physical stopping and from immediate geofence compliance, which are
not claimed. All experiments use
lightweight ROS 2 processes (plus Gazebo for physics), not physical
robots.

## 1. Introduction — practical problem

Rule rollout in fleets is a fleet-wide configuration change under a
hostile network: partitions, crashes, restarts, loss, reorder, late
delivery. The defect under test: missed updates leave robots
executing obsolete safety rules with no bound (2PC 40.4 s drive-
through in Gazebo; multi-second stale means in fault injection).
Required behavior: (i) obsolete-rule motion authorization ends within
a stated budget after supersede; (ii) partitioned/restarted robots
cannot act until reconciled; (iii) the fleet keeps making progress
when communication heals. Non-goals stated up front (no new consensus,
no hardware claims).

## 2. Related work (B3-first, then neighbors, then 2026 disclosures)

- 2PC + leases + fencing + reconciliation + HOLD as the careful
  composite baseline (B3): presented as the mechanism account of our
  own design; no superiority claimed (never implemented).
- Chubby (leases/sequencers/fencing pattern); Reitblatt + Mizrahi
  (versioned updates WITHOUT partitions — the assumption we refuse);
  RTA/Simplex/ASTM F3269 (single-system supervision, no fleet sync);
  Open-RMF lane closure (application shape, zero guarantees);
  SROS2/DDS access control (static authorization, no currency);
  geofence monitoring (single-vehicle containment).
- 2026 execution-finality I-Ds (Das, individual drafts, unreviewed):
  per-act finality at the sink, monotonic epochs, HOLD composites —
  single-platform scope delimited from fleet commit semantics; cited
  with status, not as standards.

## 3. System architecture

Coordinator (reachable-unanimity 2PC, generations, WAL, re-fence,
single replay, pull answers); agent (adopt-only-current contact
sync, restart-UNRECONCILED, pull reconcile); MotionFence
(conjunctive per-command gate + ledger); topics/messages; HOLD
state machine; steady-clock discipline.

## 4. Safety assumptions and properties

Assumption table A1–A8 (P0); I1–I7 as checked properties with exact
scope (bounded instances; I2 vacuous in T0 model, mutation-tested in
ROS); B_real decomposition; T0 theorem status (preliminary/bounded);
the trichotomy as the section's organizing principle.

## 5. Implementation

ROS 2 processes, topics/QoS (BEST_EFFORT control topics,
CONTROL_DEPTH sizing as negative result), shim fault model (in-node
deterministic impairments instead of netns/tc — disclosed deviation),
artifact layout for reproducibility.

## 6. Experimental methodology

Preregistration + dual-freeze chain; validity ledger (what each
record may/may not support); frozen schedules (matrix F0–F15 ×30,
5-robot 11, W-HEAL/W-SUSTAINED, A1/A2/A3, Gazebo Q); metrics
(contradictory, stale_max vs B_real, heal-to-commit, ledger join);
Gazebo scenario (partition → HOLD → heal → reconcile → egress →
detour). Explicit: lightweight processes, single host, Gazebo
physics only.

## 7. Results and negative findings

T0 counterexamples + elimination (bounded); matrix/30x/5-robot
margins; W-HEAL 100/100 with heal-to-commit distribution; M/N
outcomes incl. amended restart; Q witnesses with epoch-gated metric;
A-controls; THEN the negatives in full: T1 0/100 wedge + root cause,
T1.1/T1.2 verdicts, voided comparisons, downgraded transport
hypothesis, unexplained-but-bounded RSS, uncounted ACKs, missed QoS
captures — each with its lesson (feeds C2).

## 8. Limitations

Seven unsupported classes (P0 claim matrix §2); single-host clocks;
Gazebo-only physics; no B3/B4 implementation comparison; guard/jitter
budgets unstressed; permanent-loss tails inconclusive; SCOPE
quarantine note.

## 9. Conclusion

Restate C1–C3 in B3-honest language; trichotomy as takeaway;
no novelty, optimality, or compliance claims beyond the evidence.

 relates-to: CONTRIBUTION_MATRIX C1–C3; evidence: P0 claim matrix.
