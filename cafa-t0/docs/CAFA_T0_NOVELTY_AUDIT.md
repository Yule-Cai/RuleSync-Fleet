# CAFA-T0 Novelty Audit (Phase A)

Date: 2026-10-14. Frozen BEFORE algorithm design. Primary sources
accessed via publisher/arXiv/author pages (links below); claims below
report what those sources state, not secondhand summaries. Verdict
rationale at the end. This audit does NOT claim novelty — it records
collisions honestly so gates G1/G7 can be adjudicated.

## Collision matrix

### N1. Reitblatt et al., "Abstractions for Network Update", SIGCOMM 2012
- Link: https://doi.org/10.1145/2342356.2342427
  (also https://conferences.sigcomm.org/sigcomm/2012/paper/sigcomm/p323.pdf)
- Problem: configuration changes in SDNs step through incorrect
  intermediate configurations (outages, loops, security holes).
- Mechanism: per-packet consistency (every packet sees exactly one
  global configuration) and per-flow consistency; two-phase update
  with version stamping; proof that per-packet consistency preserves
  ALL trace properties (Coq-verified).
- Guarantee: logical/configurational — trace-property preservation
  across the update. No physics, no time, no robots.
- Difference from CAFA: packets are stateless and interchangeable;
  robots have inertia, braking distance, footprints, and leases.
  Per-packet consistency has no notion of a "physically infeasible
  activation instant", downtime, preparatory evacuation, partitioned
  (unreachable) participants, or shared-resource conflicts.
- Verdict: PARTIAL overlap (the commit/prepare/activate trichotomy
  and versioned-config ideas rhyme). Genuinely distinct problem
  (physical fleet activation under communication uncertainty).

### N2. Mizrahi, Saat & Moses, "Timed Consistent Network Updates",
SOSR 2015 (extended: IEEE/ACM Trans. Networking 24(6), 2016,
3412–3425; arXiv:1505.03653)
- Link: https://dl.acm.org/doi/pdf/10.1145/2774993.2775001
- Problem: consistent SDN updates with lower overhead/better
  scalability than untimed order/two-phase.
- Mechanism: time-triggered phases (time-based order, time-based
  two-phase) using synchronized clocks (PTP/GPS); controller need
  not wait for phase completion; inconsistency metric for the
  consistency–scalability tradeoff knob.
- Guarantee: same logical consistency as untimed methods, shorter
  update duration (lemmas on δ vs Dc), 50-node testbed.
- Difference from CAFA: the timed instant is chosen for OVERHEAD
  (rule-duplication time), never for PHYSICAL FEASIBILITY. No robot
  dynamics, braking, reachable sets, partitions with stale leases,
  shared corridors, or downtime minimization. Clock sync is assumed
  accurate; CAFA must handle clock skew as uncertainty.
- Verdict: PARTIAL overlap (timed activation instant is the closest
  single mechanism to CAFA's activation time). Distinct: CAFA's T is
  constrained by worst-case physical certificates and joint fleet
  coupling, not table occupancy. **This is the highest-risk
  collision: if CAFA reduces to "timed update + braking check",
  G7 fails by the brief's own critical rule.**

### N3. Černý, Foster, Jagnik & McClurg, "Optimal Consistent Network
Updates in Polynomial Time", 2016 (arXiv:1607.05159; LNCS 2016)
- Link: https://arxiv.org/abs/1607.05159
- Problem: maximal-parallelism switch-update ordering preserving
  per-packet consistency.
- Mechanism: polynomial-time optimal consistent order update
  (vs NP-completeness for loop-freedom/waypoint variants).
- Guarantee: optimality of parallelism under per-packet consistency.
- Difference from CAFA: ordering of CONFIGURATION writes, not
  physical preparatory maneuvers; no dynamics, uncertainty, leases,
  deadlines with physical meaning, or cost beyond parallelism.
- Verdict: DISTINCT (ordering problem, not activation problem).
  Useful only as a conceptual ancestor of "optimal update sequencing".

### N4. Ballotta & Talak, "Safe Distributed Control of Multi-Robot
Systems With Communication Delays", IEEE TVT 74(7), 2025, 10137–10150
- Link: https://doi.org/10.1109/TVT.2025.3546857
  (also arXiv:2402.09382)
- Problem: learned distributed CBF controllers degrade under
  communication delays; formalize distributed CBF + predictor
  (state projection with Age-of-Information) to restore safety rate.
- Mechanism: distributed CBF certificate + GNN controller +
  AoI-tagged predictor, alternating training; collision avoidance.
- Guarantee: improved empirical safety rate (not zero-violation
  proof under delay); formal distributed-CBF characterization under
  local communication.
- Difference from CAFA: NO rule update anywhere — the safety set is
  FIXED; the problem is delay-robust tracking of it. No epochs,
  leases, activation instants, preparatory evacuation, downtime
  objective, or partitioned-unreachable participants (delays, not
  partitions; predictor needs eventual delivery).
- Verdict: DISTINCT problem (delay-robust control, not rule
  activation). Shares only the vocabulary (certificates, delays).

### N5. Mestres, Nieto-Granda & Cortés, "Distributed Safe Navigation
of Multi-Agent Systems Using Control Barrier Function-Based
Controllers", IEEE RA-L 9(7), 2024, 6760–6767
- Link: https://arxiv.org/html/2402.06195v2
- Problem: distributed CBF synthesis for navigation with coupled
  safety constraints (obstacles + teammates).
- Mechanism: state-dependent network optimization with auxiliary
  mismatch variables + projected saddle-point dynamics; local QPs.
- Guarantee: safety at all times + asymptotic convergence to the
  centralized optimum (under perfect local communication).
- Difference from CAFA: static safety set, perfect communication,
  no rule change, no activation time, no leases/partitions, no
  downtime objective. The coupling technique (auxiliary-variable
  decoupling) is a candidate IMPLEMENTATION tactic for CAFA's joint
  planner, not the same problem.
- Verdict: DISTINCT problem; POTENTIAL mechanism donor (decoupled
  joint optimization). Using it must be cited as such.

### N6. Kim, Lee & Ames, "Safety-Critical Coordination of Legged
Robots via Layered Controllers and Forward Reachable Set based
Control Barrier Functions", ICRA 2024, 3478–3484
- Link: https://arxiv.org/abs/2312.08689
  (doi:10.1109/ICRA48506.2024.10610589)
- Problem: safe coordination of legged robots in dynamic
  environments (locomotion-grade).
- Mechanism: top-level HOCBF planner on forward reachable sets +
  SRB middle planner + whole-body low level; per-agent
  safety-ensured trajectories.
- Guarantee: coordination safety via FRS-grounded HOCBFs (sim +
  hardware).
- Difference from CAFA: no rule updates, no fleet-wide activation
  instant, no communication/lease uncertainty model, no shared
  corridor reservation across a rule transition, no downtime
  objective. FRS usage is the closest certificate TECHNOLOGY.
- Verdict: PARTIAL overlap (FRS-based certificates). Distinct
  problem; FRS tubes are a donor technology, to be cited.

### N7. Open-RMF lane closures / speed-limit updates + VDA5050
- Links: https://github.com/open-rmf/rmf_ros2/pull/15 (lane closure),
  https://github.com/open-rmf/rmf_ros2/pull/217 (speed limits),
  https://github.com/VDA5050/VDA5050 (fleet interface incl. map
  pre-load/buffer + enable-by-instant-action, order base/horizon
  stitching under lossy MQTT).
- Problem: industry mechanisms for closing lanes / limiting speeds /
  swapping maps in running fleets.
- Mechanism: LaneRequest/SpeedLimitRequest topics; retreat-to-lane-
  start + replan on closure; map pre-load then instant-action enable.
- Guarantee: EXPLICITLY WEAK — Open-RMF notes "we do not offer very
  strong guarantees about the effectiveness or reliability" of
  closure retreat; VDA5050 assumes base already executed under
  lossy MQTT.
- Difference from CAFA: mechanisms WITHOUT certificates, WITHOUT a
  notion of physically feasible activation instants, WITHOUT joint
  downtime optimization, WITHOUT lease/partition semantics.
- Verdict: NO collision — this is the MOTIVATING GAP (what industry
  does without guarantees is exactly what CAFA must certify).
  Cited as baseline context (B3-flavored practice).

### N8. Runtime assurance / dynamic-spec линии
- gatekeeper (Agrawal & Panagou, IEEE TRO 2024;
  https://websites.umich.edu/~dpanagou/assets/documents/DAgrawal_TRO24.pdf):
  single-robot committed-trajectory + backup-set finite-horizon
  certificates under online sensing. CLOSEST certificate SHAPE to
  CAFA's (commit/prepare/activate maps to committed/candidate/backup
  trajectories). Differences: single agent (no fleet coupling, no
  shared resources, no communication/lease uncertainty, no joint
  downtime objective). PARTIAL overlap; donor + must-cite.
- Dynamic shielding for parametric specs (arXiv:2505.22104, 2025):
  offline atomic shields + online composition for evolving safety
  sets, single-robot nav. Differences: spec-SWITCHING (not fleet
  activation), no communication/lease model, no joint optimization.
  PARTIAL overlap; distinct problem.
- Emergency-Brake Simplex (Shen & Wang, arXiv:2501.01831, 2025):
  abrupt reachability-constraint changes handled by KKT/IPM
  reference-state re-optimization, single system. Differences: no
  fleet, no communication, no leases, no joint activation planning;
  optimization-for-feasibility rather than joint downtime/latency
  planning. PARTIAL overlap (closest "rule change at runtime"
  relative); distinct problem.
- Optimal RTA via RL (Mitra et al., ICCPS 2024): single-plant
  switching-policy optimization, RL-based. Different object and
  method class (CAFA round forbids NN training). DISTINCT.
- NeRTA (El Yaacoub et al., 2023): schedule-invariant SOFTWARE
  updates for robot control loops (idle-time scheduling). Different
  object (code updates, not safety-rule activation). DISTINCT.
- Kröger et al., FMICS 2025 (contract-based CPS runtime updates,
  downtime minimization via inactive states; doi
  10.1007/978-3-032-00942-5_11): closest "update + downtime"
  relative. Differences: single CPS/components (not fleet),
  contract modes (not physical reachable certificates under
  communication uncertainty), no leases/partitions/shared
  resources. PARTIAL overlap; distinct problem.
- UMBRELLA (2026), STL-KCBS, recurring-LTL coordination (2024–26):
  mission/task-spec replanning (LTL/STL), NOT hard safety-rule
  activation with physical certificates + leases. DISTINCT.

## Verdict rationale (pre-implementation)

No single work solves information-constrained JOINT physical-rule
activation: timed updates (N2) lack physics/leases/coupling;
certificates (gatekeeper, N6, N8) are single-robot without fleet
communication semantics; fleet mechanisms (N7) lack guarantees;
update-timing works (NeRTA, Kröger) lack physical certificates and
fleet coupling. The conjunction — joint preparatory planning +
worst-case tubes under lease/partition uncertainty + shared-resource
coupling + downtime/latency optimization under a deadline — is not
found as one algorithm. NOVELTY NOT YET ESTABLISHED (that requires
G1/G7 after results): the audit binds CAFA to demonstrate (a) strict
advantage on coupled families (G3), (b) non-vacuous coupling (G5),
and (c) irreducibility to timed-updates-plus-braking (G7, with S10
as the tripwire: if the optimum equals timed activation broadly,
report NOVELTY_WEAK even with wins elsewhere).
