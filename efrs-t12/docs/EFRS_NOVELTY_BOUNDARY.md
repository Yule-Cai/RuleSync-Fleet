# EFRS Novelty Boundary — T1 Update (no collision claimed)

This update addresses the now-important 2026 LiDAR hard-bank paper
(Yilmaz & Aydogmus, Robotics and Autonomous Systems, July 2026:
auditable LLM-guided Pareto scenario discovery + hard-bank
fine-tuning for robust map-free LiDAR navigation), plus Open-RMF and
adjacent fleet coordination, against the narrowed candidate claim.

## Standing disclaimers (unchanged, all generic prior mechanisms)

Leases, fencing tokens, 2PC, crash recovery, ROS2 QoS DDS transport,
robot fleet adapters, heartbeat/renewal messaging — none claimed.

## The 2026 hard-bank paper, distinguished

That work mines hard navigation SCENARIOS (LLM-guided, Pareto-ranked,
auditable) and fine-tunes a navigation policy on the resulting hard
bank. Three structural differences from EFRS:

1. Mined object: traffic/navigation scenarios vs SCOPE's
   sensor-coordinate censor OPERATORS. Scenario mining asks "in which
   situations does the policy fail"; operator mining asks "which
   sensor-coordinate deletions flip this frozen policy's action".
2. Target of robustness: navigation-scene generalization vs
   leave-family-out SENSOR DEGRADATION (structured observation
   corruption families never seen in training).
3. Machinery: no rule epochs, no snapshot hashes, no leases, no
   fencing tokens, no required_epoch motion gate, no bounded-staleness
   claim, no reconcile-before-motion. Hard-bank mining/fine-tuning
   ITSELF is therefore explicitly NOT SCOPE's contribution — it is the
   M1-style baseline any competent lab would run, which is why this
   round includes HardGeneric as a named comparator rather than as
   background.

Related scenario-mining/fine-tuning lines (AdvSim adversarial LiDAR
scenarios + retraining; closed-loop adversarial curricula E2E2;
responsibility-attributed CARS; AutoMine/SceneMiner mining-only):
same verdict — scenario-level mining with retraining, none of them a
sensor-coordinate operator envelope with epoch-fenced motion
authorization and mandatory reconciliation.

## Open-RMF fleet/task coordination, distinguished

Open-RMF coordinates tasks, traffic lanes, and resource claims across
heterogeneous fleets. It does not version hard safety rules by epoch,
does not fence motion on rule currency, and makes no bounded-staleness
claim under partitions. Composable future infrastructure (brief
explicitly defers integration), not overlapping subject matter.

## Distributed locking/fencing, REDACT, dynamic geofences

Locking/fencing primitives and REDACT's masking+gating remain
infrastructure lineage (see T0 audit). Dynamic geofence / lane-closure
mechanisms found to date are single-system traffic controls without
fleet epoch versioning or partition-bounded staleness. No collision.

## Candidate claim (current, narrow)

Bounded stale hard-rule execution in networked robot fleets through
rule-epoch-fenced motion authorization and mandatory
post-partition/restart reconciliation — evidenced by the T0
counterexample elimination and, pending T1 gates, ROS2 fault-injection
results. If T1 lands ENVELOPE_ONLY_SUPPORTED, the claim drops
adversarial search and becomes sensor-coordinate structured corruption
randomization for leave-family-out degradation; that simplified claim
is then re-checked against domain randomization / masked training, and
NOVELTY_WEAK is reported if it does not survive. No paper claim is
made in T1 under any outcome.

## T1.2 Update (2026-10-14): recovery engineering explicitly disclaimed

The following are generic distributed-systems mechanisms, explicitly
NOT claimed as novel in any EFRS publication, regardless of round
outcome: retry, abort/retry, message deduplication, idempotence,
queue sizing, backpressure avoidance, leases, fencing tokens, 2PC,
WAL, reconciliation. The T1.2 recovery changes (bounded-rate
generation retry, single-shot publications, control-depth sizing,
local safety ledger) exist only to make the implementation deployable
under eventual heal. Do NOT claim congestion-control novelty: the
depth-48 sizing did not survive contact with sustained loss (T1.2
interim §20) and is recorded as a negative result, not a contribution.

The paper-level candidate claim remains: epoch-fenced hard
safety-rule execution at the robot motion boundary, with bounded
stale-rule motion and mandatory reconciliation after
network/restart faults.
