# EFRS-P0 Prior-Art Matrix (claim-level, primary-source citations)

Scope: read-only audit. No novelty is claimed from a missing matching
title. Unreviewed preprints and Internet-Drafts are recorded as prior
technical disclosures with their actual status, never as adopted
standards. All URLs verified live 2026-10-15.

Status key: [PUB] peer-reviewed/standard; [DOC] stable technical
documentation; [PRE] unreviewed preprint/project; [ID] individual
Internet-Draft (no IETF standing, not WG-adopted, not peer-reviewed).

---

## 1. Google Chubby (OSDI 2006) [PUB]

- Sources: M. Burrows, "The Chubby lock service for loosely-coupled
  distributed systems", OSDI 2006.
  https://research.google.com/archive/chubby-osdi06.pdf ;
  https://www.usenix.org/conference/osdi-06/chubby-lock-service-loosely-coupled-distributed-systems
- Exact problem: coarse-grained locking + low-volume reliable storage
  for loosely-coupled distributed systems; delayed/reordered requests
  acting without lock protection after holder failure.
- Assumptions/failure model: asynchronous, processes fail
  independently; single-master cell with majority consensus; master
  leases; client clocks advance within a known factor of server clocks.
- Mechanism: sessions with KeepAlive-blocked lease renewal; locks with
  generation numbers; **sequencers** (opaque lock+mode+generation
  strings) that recipient servers must check before acting; lock-delay
  after failure-triggered release; new master waits out worst-case
  lease before serving.
- Guaranteed property: at most one lock holder's effects are honored by
  checking servers; stale-holder requests rejected by sequencer
  comparison; session-cache safety via lease + grace period.
- Epochs/fencing: lock generation number inside the sequencer IS a
  fencing epoch; servers keep highest-seen sequencer. Re-fencing after
  failover via worst-case-lease wait.
- Actuation enforcement: none physical; enforcement at recipient
  software servers (file servers), advisory for unmodified servers.
- Partition/restart: client in jeopardy on local lease-timeout expiry
  (empties/disables cache); master failover re-election with lease
  wait; sessions recreated without on-disc state after the fix.
- Explicit limitations: sequencers require recipient cooperation;
  lock-delay is imperfect protection for legacy servers; no bound on
  physical effects (no actuators).
- Exact overlap with EFRS: session lease + renewal; generation/fence
  comparison at the effect boundary; restart re-fencing discipline;
  lease-timeout ⇒ self-suspension (jeopardy ≈ HOLD).
- Remaining difference: object fenced is a data lock/sequencer, not a
  fleet rule snapshot; no motion gate, no per-command epoch+hash check,
  no bounded-staleness property, no reconcile-before-motion, no 2PC
  update protocol, no fleet commit semantics.

## 2. Reitblatt et al., consistent network updates (SIGCOMM 2012) [PUB]

- Sources: M. Reitblatt, N. Foster, J. Rexford, C. Schlesinger,
  D. Walker, "Abstractions for Network Update", SIGCOMM 2012.
  https://www.cs.cornell.edu/~jnfoster/papers/consistent-updates-sigcomm12.pdf ;
  https://dl.acm.org/doi/10.1145/2342356.2342427
- Exact problem: configuration changes stepping through incorrect
  intermediate configurations; guarantee each packet sees exactly one
  consistent global configuration.
- Assumptions/failure model: reliable SDN controller; OpenFlow
  switches; version-tag bits available; NO partitions, NO crashes of
  the controller in the model, no actuators.
- Mechanism: per-packet consistency abstraction; two-phase update
  (install new config internally keyed on version tag, then flip
  ingress stamping); Coq-verified trace-property preservation.
- Guaranteed property: every packet processed under old OR new config,
  never a mixture; all trace properties holding before+after hold
  throughout.
- Epochs/fencing: version tag ≈ epoch; no fencing (no stale-holder
  threat model — old-version packets simply drain).
- Actuation enforcement: none (forwarding only, fully reversible).
- Partition/restart: out of scope.
- Explicit limitations: packet-level only; assumes spare tag bits and
  flow-table room; says nothing about actuator commitment.
- Exact overlap with EFRS: versioned configurations; two-phase
  prepare/commit shape; "never a mixture" ≈ epoch equality per act.
- Remaining difference: per-packet stateless forwarding vs per-robot
  stateful motion authorization; no leases, no fencing generations, no
  bounded staleness under partition, no restart semantics, no
  reconciliation, no physical irreversibility. The EFRS problem (stale
  RULE execution by partitioned robots) does not exist in this model.

## 3. Mizrahi–Saat–Moses, timed consistent updates (SOSR 2015) [PUB]

- Sources: T. Mizrahi, E. Saat, Y. Moses, "Timed Consistent Network
  Updates", SOSR 2015 (extended arXiv:1505.03653).
  https://arxiv.org/abs/1505.03653
- Exact problem: reduce overhead/duration of consistent updates using
  accurate time (PTP/ReversePTP/GPS + TimeFlip scheduling).
- Assumptions/failure model: synchronized clocks (microsecond-scale
  scheduling accuracy); reliable controller-to-switch messaging;
  update phases scheduled at T1<T2<T3.
- Mechanism: time-triggered phases (time-based order, time-based
  two-phase); inconsistency metric I for the simultaneous-update
  corner; Scheduled Bundles (OpenFlow 1.5).
- Guaranteed property: same per-packet consistency as Reitblatt at
  lower overhead; inconsistency bounded by I where simultaneity used.
- Epochs/fencing: scheduled times act as implicit epochs; no fencing
  tokens; relies on clock sync, not on stale-holder rejection.
- Actuation enforcement: none.
- Partition/restart: out of scope (controller connectivity assumed).
- Explicit limitations: needs PTP-class sync; inconsistency window
  [T−Dn, T] for simultaneous updates.
- Exact overlap with EFRS: phased versioned update; scheduled/known
  timing structure.
- Remaining difference: EFRS uses NO cross-node clock sync for safety
  (lease expiry is local-monotonic per robot); timed updates assume
  exactly what EFRS refuses to assume (synchronized clocks, connected
  controller). Opposite design trade, same update-shape ancestry.

## 4. Fencing tokens: Kleppmann formulation + etcd/ZooKeeper practice

- Sources: M. Kleppmann, "How to do distributed locking", 2016
  (widely-cited formulation of the fencing-token requirement).
  https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html ;
  Chubby sequencers (§1 above) as the primary mechanism source;
  ZooKeeper lock recipe (ephemeral sequential znodes; creation
  zxid/sequence as token)
  https://zookeeper.apache.org/doc/current/recipes.html#sc_recipes_Locks
- Exact problem: paused/partitioned lock holders acting after lease
  expiry (GC pause, VM suspend, queued writes).
- Mechanism: monotonically increasing token per acquisition; protected
  resource stores highest-seen token and rejects lower (atomic
  compare-and-set at the resource; etcd revision / ZK zxid as token
  source).
- Guaranteed property: stale holder's writes mechanically rejected at
  the point of effect, independent of timing assumptions.
- Exact overlap with EFRS: EFRS `fence` generation + `fence_seen`
  max-tracking + reject-lower is this pattern with (epoch→ruleset,
  resource→motion authorization). Coordinator restart re-fence (+1) is
  the "never reissue / persist the counter" rule.
- Remaining difference: classical fencing guards idempotent data
  writes; EFRS applies the pattern to motion authorization with a
  time-bounded lease (fence alone does not bound staleness — the lease
  does) plus hash-bound payloads. The RESOURCE-side check placement
  ("check happens at the point of actual effect") is shared exactly:
  MotionFence is the resource-side checker.

## 5. Runtime Assurance: Simplex / RTA / ASTM F3269 [PUB/DOC]

- Sources: D. Seto et al., "The Simplex Architecture for Safe Online
  Control System Upgrades", ACC 1998; L. Sha, "Using Simplicity to
  Control Complexity", IEEE Software 2001; ASTM F3269-21, "Standard
  Practice for Methods to Safely Bound Behavior of Aircraft Systems
  Containing Complex Functions Using Run-Time Assurance"
  https://store.astm.org/f3269-21.html ; RTA revision philosophy
  (Littlefield, DLR/AIAA SciTech)
  https://elib.dlr.de/144352/1/latestsubmission_v1_ASTM%20F3269_SciTech_Control-ID_3453655.pdf
- Exact problem: certify systems containing uncertifiable complex
  functions by bounding them at runtime (monitor + switch to assured
  recovery).
- Mechanism: Complex Function vs assured Safety Monitor + RTA Switch +
  Recovery Function(s); composable per-subsystem assurance.
- Guaranteed property: system output stays within assured bounds while
  monitor/switch/recovery are assured; certification strategy, not a
  protocol.
- Epochs/fencing: none (no versioning, no fencing tokens).
- Actuation enforcement: yes — output switching at the control
  boundary (single-system).
- Partition/restart: out of scope (single platform assumed coherent).
- Explicit limitations: says nothing about distributed agreement,
  fleet coordination, versioned rule rollout, or partitions.
- Exact overlap with EFRS: MotionFence-as-supervisor shape (gate at
  the motion boundary + HOLD as recovery output); HOLD-as-safe-state.
- Remaining difference: single-system, no epochs/leases, no fleet,
  no update protocol, no bounded-staleness-across-versions property,
  no reconciliation. EFRS's distributed half is entirely absent.

## 6. Open-RMF lane closures (2021–) [DOC]

- Sources: open-rmf/rmf_ros2 PR #15 (fleet adapters close/open nav-graph
  lanes at runtime; retreat-to-lane-start + replan)
  https://github.com/open-rmf/rmf_ros2/pull/15 ; design discussion
  https://discourse.openrobotics.org/t/lane-closure-13/44946
- Exact problem: close navigation lanes fleet-wide at runtime and
  reroute affected robots.
- Assumptions: connected fleet manager; best-effort propagation;
  cooperative adapters.
- Mechanism: LaneRequest / ClosedLanes topics; adapter-triggered
  replan; reverse-to-lane-start for robots on closed lanes.
- Guaranteed property: NONE formal — PR text: "We do not offer very
  strong guarantees about the effectiveness or reliability of this
  behavior"; replanning may fail (impossible-plan crash, issue #248).
- Epochs/fencing: none. No versioning of the closure set, no currency
  checks, no leases.
- Actuation enforcement: none at the boundary (planner-level only).
- Partition/restart: unhandled (a partitioned robot keeps its old
  graph with no bound — precisely the EFRS stale-rule window).
- Exact overlap with EFRS: runtime safety-rule (closure) rollout to a
  ROS2 fleet — the application shape.
- Remaining difference: everything load-bearing (epochs, hashes,
  leases, fence gate, bounded staleness, reconcile). Open-RMF is the
  closest APPLICATION neighbor and the clearest demonstration that the
  application alone does not supply the guarantees.

## 7. Runtime geofence monitoring (Torens et al.; dynamic geofences)

- Sources: C. Torens et al., "Geofencing requirements for onboard safe
  operation monitoring", CEAS Aeronautical Journal 2020
  https://link.springer.com/article/10.1007/s13272-020-00451-0 ;
  α-shape/Voronoi dynamic geofencing (Deloitte/UAV, arXiv 2110.09453)
  https://ar5iv.labs.arxiv.org/html/2110.09453
- Exact problem: contain a UAS in/away-from geographic volumes;
  monitor-then-mitigate (contingency → termination), dynamic buffers.
- Mechanism: onboard monitoring of position vs volumes; mitigation
  ladder; dynamic safety borders.
- Guaranteed property: single-vehicle containment modulo
  buffer/monitoring assumptions.
- Epochs/fencing: none. Geofence CONTENT updates across a fleet under
  partition are not modeled (database refreshed pre-flight or online
  without versioning discipline).
- Exact overlap with EFRS: KEEP_OUT semantics of hard rules; HOLD/
  terminate as safe state.
- Remaining difference: single-vehicle, no versioning, no fleet
  agreement, no bounded cross-version staleness, no reconciliation.

## 8. SROS2 / DDS Security access control [DOC]

- Sources: ROS 2 access-control policies design doc
  https://design.ros2.org/articles/ros2_access_control_policies.html ;
  ROS 2 DDS-Security integration
  https://design.ros2.org/articles/ros2%5Fdds%5Fsecurity.html
- Exact problem: authenticate participants; authorize publish/
  subscribe/service/action operations by signed policy (MAC, deny
...[truncated 9113 chars]