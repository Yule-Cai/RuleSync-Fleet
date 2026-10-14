# EFRS-T1.3 Preregistration — Transaction-Transport Isolation Gate

Date: 2026-10-14. Frozen BEFORE any T1.3 implementation or experiment.
Parents: `efrs-t12/docs/EFRS_T12_FINAL_RESEARCH_DECISION.md` (T1.2 FAIL,
G4 FAIL adjudicated), T1.1/T1.2 contracts still binding where not
superseded below.

## Purpose (§B authorization)

Determine whether DDS RELIABLE transaction transport is the binding
cause of the T1.2 W-HEAL liveness collapse. Exactly ONE design
dimension changes: transaction-control topic ReliabilityQoS. All
application protocol semantics bit-for-bit/semantically identical
(txn_id, one-PREPARE/generation, one-VOTE/robot/txn, 1500 ms deadline,
timeout ABORT, 100 ms re-attempt, one COMMIT, one ACK/robot/txn,
leases, contact-sync, reconcile, WAL, I1–I7, B_real, queue-depth
formula with N=20→48, both workloads, 3 s loss caps, 10 s recovery
bound, 100 sequential updates). Unchanged: depth, threads, topology,
heartbeat, lease, deadline, retry rate, fault schedules, robot count.

## QoS delta (§C, the single change)

Transaction-control topics PREPARE/VOTE/ABORT/COMMIT/ACK:
RELIABLE → BEST_EFFORT, VOLATILE durability, KEEP_LAST history, SAME
CONTROL_DEPTH. No TRANSIENT_LOCAL. Rationale (frozen): omission is
already handled by timeout/abort/retry/lease/reconcile, so
transport-level guaranteed retransmission is not required for safety.
Non-transaction topics (state/renew/reconcile/motion/admin/ledger)
unchanged; paired-endpoint compatibility touched only within the same
transaction topic if strictly required (symmetric change needs none).

## Claim boundary (§B)

SAFETY: obsolete authorization fenced within B_real. CONDITIONAL
LIVENESS (unchanged): GST + operational + reachable + eventually
delivered ⇒ pending update terminates, progress resumes. BANNED:
permanent-partition progress, non-blocking atomic commit under
arbitrary faults, async-partition consensus, retries-as-novel.

## Source contracts (§D, AST + runtime)

PREPARE/VOTE/ABORT/COMMIT/ACK pubs+subs: BEST_EFFORT, VOLATILE,
KEEP_LAST, frozen depth; zero RELIABLE transaction endpoints remain;
depth formula unchanged. Any accidental change to deadline/lease/
retry/quorum/state-machine fails the contract tests. Runtime proof:
`ros2 topic info -v` captures for all five topics in BOTH configs
(R shows RELIABLE, B shows BEST_EFFORT).

## Instrumentation (§E, non-semantic, passive only)

Host-side podman stats (5 s: CPU/RSS/NET) + podman top (30 s,
per-process) during formal runs; ROS send/receive/callback counts
from node logs; FastDDS HEARTBEAT/ACKNACK/NACKFRAG only if enabling
them changes nothing material, else loopback pcap if tcpdump exists,
else app-level counters (record which path was taken). No injected
traffic. Diagnostic bar: RELIABLE shows persistent RTPS reliability
meta-traffic/backlog while BEST_EFFORT does not. Mechanism evidence
is DIAGNOSTIC; PASS never requires proving a vendor bug.

## Micro-gate (§F, diagnostic, 1x each, no tuning from it)

20 robots; T1.2 W-HEAL first fault segment (loss_random p=0.2 seed 5,
t=5.0–8.0); timed proposes (8 epochs every 2 s from t=1.5); duration
30 s (covers pre-fault + 3 s loss + ≥10 s post-heal). R = frozen T1.2
code, B = T1.3 code; nothing else differs. Record messages, votes
received, aborts, commits, CPU/RSS, meta-traffic diagnostics.

## Model (§G)

T1.2 model carried over: transport retransmission was never modeled
(single abstract delivery unless dropped), so BEST_EFFORT changes
nothing representable — documented equivalence, not an omission.
Re-run T0-9 + K1–K10 + G-a..G-f + J + fuzz (200 seeds). ADDED: triple
loss in one attempt (PREPARE+VOTE+COMMIT dropped, heals, gen-1
commits) and commit-loss-then-clean-heal convergence. Liveness monitor
only on EVENTUAL_HEAL; permanent-loss = safety/HOLD only. Mandatory:
I1–I7 zero, fuzz clean. TLC supplemental.

## Workloads (§H, byte-identical sched copies)

W-SUSTAINED: exact T1/T1.2 trace (safety only). W-HEAL: T1.2 file
(GST=248.02, sequential 1..100, cap 600 s). Sequential-issue,
propose/reattempt/abort/commit accounting unchanged.

## Recovery measurement (§J, frozen definitions)

 healable pending update = an update proposed before a heal instant
(partition/loss until, restart completion, or global GST) that was
uncommitted at that instant. T_heal_to_commit = T_COMMIT − T_heal.
Report max/P50/P95/P99 over all such pairs; GATE ON MAX ≤ 10 s.

## Resource gate (§K, frozen)

RSS_second_half_mean ≤ 1.25 × RSS_first_half_mean over the run
excluding t<60 s startup warmup; no killed/OOM processes; no
continuously increasing transaction backlog (uncommitted issued count
must return to 0 given G3); callback starvation >10 s post-heal is
ENTAILED by G3+G5 (any such starvation would stall commits or breach
the bound — documented here so K adds only the RSS/OOM/backlog
measurements). CPU descriptive only.

## Replay/scales/regressions/witness (§§K–Q)

K13: same gen-scoped 13/20 sched on T1.3 (g0 abort → auto gen →
commit, no stale violation). M-gate: N/O/P run ONLY after model +
W-SUSTAINED + W-HEAL + resource + K13 all pass. N: F0–F15 ×30 + A3
(bug reproduces only under A3). O: frozen 5-robot + I2 (reject +
HOLD/reconcile). P: witness 3/3 on final EFRS only; T1 Plain2PC
reused (no rerun/retrofit).

## Gates (§Q; ANY fail → STOP; forbidden escapes listed in
authorization §Q verbatim and binding)

G1 model. G2 13/20 replay. G3 W-SUSTAINED ledger-clean. G4 W-HEAL
100/100. G5 heal-to-commit max ≤10 s. G6 resource gate. G7 100%
ledger coverage, zero unverifiable ACCEPT. G8 3-robot. G9 5-robot+I2.
G10 A3 control. G11 witness 3/3.

## Deliverables (§U)

`efrs-t13/reports/EFRS_T13_REPORT.md`,
`efrs-t13/reports/efrs_t13_results.json` (22 items verbatim).
Verdict EFRS_T13_PASS / EFRS_T13_FAIL only.
