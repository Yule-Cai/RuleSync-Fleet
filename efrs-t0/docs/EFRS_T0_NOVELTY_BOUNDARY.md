# EFRS-T0 Novelty Boundary (audit for Gate 7; no novelty claimed outright)

Candidate conjunction (ALL required for a collision):

    (a) fleet rule-snapshot versioning {epoch, hash, hard_rules}
    (b) lease + fence + required_epoch motion gate + reconcile protocol
    (c) bounded stale-rule execution under partitions (I5) with
        counterexample-driven verification against 2PC/broadcast.

Explicitly disclaimed alone: leases, fencing epochs, 2PC, quorum votes,
motion gating as a concept, consensus itself. Raft/Paxos, if ever used,
is infrastructure only.

## Nearest neighbors (all differ structurally)

- Fleet lease/fence actuator gating (e.g. warehouse-fleet claim layers
  with fencing epochs + leases + stale-fence rejection at the
  actuator): same fencing PATTERN, different object. Those gate
  per-resource claims through a store; EFRS versions fleet-wide RULE
  snapshots, gates motion on epoch equality + lease liveness, bounds
  stale execution after commits (I5), and reconciles reconnecting
  robots (I7) — with no database in the loop and no reliable-transport
  assumption. Pattern shared, application + guarantees differ.
- Device-sync lease/fencing designs (lease coordinator + fencing epoch
  over sync ledgers): ledger convergence for multi-device state, not
  robot motion gating under partitions; no rule snapshots, no I5-style
  bound, no reconcile-before-motion.
- Stale-leader fencing recipes (epoch-tagged writes rejected at the
  guard): the generic pattern EFRS instantiates. Prior art FOR the
  mechanism, not for the fleet-rule-sync application. Cited as
  infrastructure lineage, never as collision.
- Raft lease work (e.g. LeaseGuard): Raft-specific read/write
  optimizations with TLA+ proofs. EFRS does not modify Raft and claims
  nothing about consensus; quorum use is infrastructure.
- Fleet choreography validation (static cross-robot checks, barriers as
  rendezvous markers): design-time validation, no runtime rule sync,
  no partitions/fencing executed. Complementary, not overlapping.
- LiDAR/adversarial robustness, occlusion benchmarks: unrelated domain
  (perception attacks), no coordination content.
- Single-robot RuleSync (this project's base): 2PC + WAL + epoch/hash
  convergence for ONE participant set. EFRS's new content is exactly
  the fleet extension under partitions: the stale-rule window does not
  exist single-robot, and the base has no lease/fence/gate/reconcile.

## Conclusion

No exact prior method combining (a)+(b)+(c) was found. The T0 exit
stands: proceed to ROS2 fault-injection. If deeper review later finds
the conjunction elsewhere, that finding must be recorded as
NOVELTY_COLLISION and take precedence over this audit.
