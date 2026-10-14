# EFRS-T1.3a / T1.3 Unified Final Report

Date: 2026-10-14/15. Covers the T1.3 transaction-transport program and
its T1.3a workload-semantics correction round, through M/N/Q with two
lead-authorized surgical amendments. Original FAILs retained as
historical evidence; nothing rewritten. No publication decision is
made here.

## 1. T1.1 closeout / adjudication

- T1: SAFETY PASS / LIVENESS FAIL / OVERALL FAIL (scale-20 0/100;
  `efrs-t1/docs/EFRS_T1_RESEARCH_DECISION.md`).
- T1.1: STOP stands (12/100); permanent-loss tail reclassified
  INCONCLUSIVE FOR EVENTUAL-HEAL; 28 sustained-expiry events
  UNRESOLVED/INSUFFICIENT-OBSERVABILITY
  (`efrs-t11/docs/EFRS_T11_FINAL_RESEARCH_DECISION.md`).
- T1.2: EFRS_T12_FAIL (74/100 void-run; G4 FAIL adjudicated — recovery
  never meaningfully exercised;
  `efrs-t12/docs/EFRS_T12_FINAL_RESEARCH_DECISION.md`).
- Evidence validity: `docs/EFRS_EVIDENCE_VALIDITY_LEDGER.md` (T1.2
  W-HEAL + T1.1 replay INVALID_FOR_EVENTUAL_HEAL_LIVENESS; micro R/B
  NOT_VALID_FOR_TRANSPORT_CAUSAL_INFERENCE; T1.3a W-HEAL
  VALID_EVENTUAL_HEAL_EVIDENCE).
- Transport hypothesis: DOWNGRADED to unresolved secondary diagnostic
  (workload semantics is the primary explanation; no transport
  comparison rerun authorized).

## 2. Exact protocol delta (T1.2 over T1.1; T1.3 = +QoS only)

Freeze `219b4a7` (T1.2), `f6ba3bf` (T1.3), `2680322` (T1.3a runner
correction), `e20ba17` (A3 control), this round's restart fix (below).
T1.2: txn_id, one-PREPARE/attempt, one-VOTE/robot/txn, 1500 ms
deadline, timeout ABORT, +100 ms re-attempt, one COMMIT (+one restart
replay), one ACK/robot/txn, contact-sync tightening, CONTROL_DEPTH,
local ledger, sequential issue. T1.3: RELIABLE→BEST_EFFORT on the
five control topics (VOLATILE, KEEP_LAST, same depth) and nothing
else. T1.3a: runner honors `loss_random.until` (+GST machinery).
Amendments: A3 old-renewal branch restored to T1-exact (this doc
§17); coordinator restart replay reordered after helper defs (§15n).

## 3. Queue-depth derivation

CONTROL_DEPTH = max(32, 2N+8): one burst ≈ N votes + N ACKs + margin
(N=3→32, 5→32, 20→48). Frozen pre-results; function-tested; never
retuned (both directions forbidden).

## 4. MotionFence local-ledger schema

Per-decision JSONL (fsync before ACCEPT publication): monotonic_ns,
robot_id, local committed epoch/hash, lease deadline, required
epoch/hash, cmd_id, ACCEPT/REJECT, reject reason, reconciled,
holding, fence_seen. F1 audit joins every ACCEPT against
now≤deadline, epoch/hash equality, reconciled-and-not-holding;
100% coverage required (cmd_id join); missing/corrupt ledger ⇒
evidence-incomplete, never PASS.

## 5. Model results

T1.2 G1 (host): T0-9 rerun clean; 17/17 systematic zero I1–I7 with
commits (incl. genuine multi-abort cycles K3/K4/K5/G-f, pull
catch-up G-a, dark-hold G-c); G-c + J1–J3 exact assertions PASS;
200-seed fuzz efrs clean; baselines reproduce T0 counterexamples.
TLA attempt layer carried (single delivery collapses identically);
T1.1 TLC: 57M states, no violations, OOM (allowed subordinate
outcome). T1.3 model update: documented transport-equivalence + H-a
(triple loss, aborts=2, gen=2, commit) + H-b (pull convergence);
re-ran green (host).

## 6. Deterministic 13/20 replay (T1.3 K13)

Gen-0 votes exactly R1–R13 (13/20) → TIMEOUT-ABORT → auto gen-1 →
commit(1,g1), no manual re-propose, stale 4.7 ms. Ledger gate_ok.
G2 PASS (unchallenged since; sched reused byte-identical for any
replay).

## 7. W-SUSTAINED (exact T1 trace, T1.3 evidence)

2/100 commits (descriptive, allowed); 51 aborts / 48 reattempts;
stale_max 150.0 ms. Ledger 20/20, 1991 rows, 1632 ACCEPTs, all four
F1 counters 0, 0 unverifiable. Central-channel counters
(auth 303/invalid 21/unverifiable 282) are evidence-drop artifacts
under 91% ambient loss (adjudicated class). G5 PASS.

## 8–11. Corrected W-HEAL (T1.3a, VALID_EVENTUAL_HEAL_EVIDENCE)

100/100 distinct epochs, 100 issued, workload_valid gst-reached
(GST=248.02). 3 aborts; attempts/update 1.0. Message counts:
106 PREPARE broadcasts + 100 COMMIT broadcasts + 2,036 received
votes; 0 redrives, 0 retransmits. Per committed update ≈ 1.06
PREPARE / ~20 votes / 1 COMMIT. Heal-to-commit (heal-straddling):
max 2.06 s, p50 1.22 s (≤10 s). Propose→commit: max 5.01 s
(ep 73), p50 0.13 s, p95 0.15 s. Stale_max 263.2 ms. 274 fence
rejections. ACKs uncounted (D4 evidence-only instrumentation gap,
carried). Resources: CPU ~160–269% descriptive; RSS ratio 1.03
(2006→2066 MB, gate ≤1.25 PASS; absolute level unexplained but flat
post-warmup; T1's 400 MB was startup-phase only — invalid comparator).

## 12. Local safety-ledger results

W-HEAL: 20/20 ledgers, 31,989 rows... (see §4 audit) 6,059 ACCEPTs,
zero violations, zero unverifiable (`gate_ok`). The ledger overrules
the degraded central channel per §F (27 sustained-expiry flags +
525 unverifiable there are asymmetric-drop artifacts, now provably
so: every ACCEPT is ledger-covered and clean).

## 13. RTPS meta-traffic diagnostics

Unavailable (no tcpdump/dumpcap/tshark on host or container; FastDDS
statistics would change endpoint behavior → skipped per protocol).
App-level counters only. Mechanism evidence stays DIAGNOSTIC;
hypothesis downgraded per §1 (no vendor-bug claim, no
BEST_EFFORT-superiority claim).

## 14. 3-robot F0–F15 (M, final EFRS, 30 reps/fault = 480)

- Ledger: 480/480 gate_ok (zero violations, 100% coverage).
- Central contr flags in 11 reps (F3×1, F8×4, F9×2, F12×4):
  ALL ledger-exonerated (fence-contemporaneous records clean;
  sound authority argument recorded in analysis: cached deadlines
  can only understate liveness, never overstate).
- Stale ≤ B_real everywhere (cell maxima 0–552 ms).
- Recovery: zero violations (every heal-straddling commit ≤10 s;
  non-committed epochs only in never-healable windows).
- A1/A2 correctly fail ledger (30/153 expired; stale 6822/59 ms).
- Original M FAIL retained (A3 broken-control run preserved).

## 15. 5-robot + I2 (N)

- 8/11 full commits, safety clean (contr 0, stale ≤184 ms,
  ledgers gate_ok): C_PART_RESTART, C_PLUS_LATE, C_STALE_RECONNECT,
  P2ISO, P32, P41, PCOORD(partial, T1-consistent), I2B.
- C_LOSS_REORDER []: permanent 30% loss, T1-identical (safety-only).
- PCOORD [1]: T1-identical (6 s post-10 s-partition insufficient for
  two sequential commits in both rounds; schedule-limited).
- C_COORD_ROBOT (amended): [1,2]; restart survived (recovered
  epoch=1, ONE replay logged, propose ep2 gen0 → COMMIT ep2 at
  +0.18 s post-restart); contr 0; stale 58.6 ms; rollbacks 0;
  ledger gate_ok (234/234). Teardown RCLError only (universal
  runner kill_all signature, post-COMMIT).
- ORDER DEVIATION (disclosed, adjudication requested): the
  CORR/DIAG executions ran BEFORE this amendment's commit (agent
  sequencing error; the T1.3a freeze workflow was otherwise
  commit-then-execute throughout). Code identity proven post-hoc:
  executed files byte-identical to reviewed local copies and
  unmodified since (mtimes predate runs; diffs recorded in commit).
  No tuning occurred between execution and commit. The evidence
  stands or falls on lead adjudication of this deviation.
- F8/F9 diagnostics (once each): [1,2] / [1] (second propose(1)
  correctly refused post-commit), contr 0, ledgers clean.
- N verdict: N_PASS_WITH_RESTART_AMENDMENT (original N FAIL retained).

## 16. I2 integrity

I2/I2B: same-epoch/different-hash + mutated payload rejected
(341/230 fence rejections), stale 41/89 ms, commits [1]/[1,2]
(legitimate epochs unaffected), safe HOLD/reconcile, no
inconsistent authorization.

## 17. A3 renewal-bug control

- Broken run: 168 ms (implementation error: inverted old-renewal
  adopt semantics; preserved).
- Amendment: `docs/EFRS_T13A_A3_POSITIVE_CONTROL_AMENDMENT.md`;
  restored T1-exact extend-without-adopt; 2 AST proofs green.
- Corrected run (exactly once, frozen sched): stale_max **7792.2 ms**
  (> B_real ✓); R3 214 unadopted renewals, committed stuck at 1
  while fleet=2 (36 stale samples, shape-matched to T1's 7830.8 ms);
  ledger gate_ok (189/189 — correctly NOT read as safe, per
  decision: locally-valid old-epoch motion IS the bug mechanism).
- A3_CONTROL_REPAIRED_AND_REPRODUCED. A3_CONTROL_FREEZE_COMMIT =
  e20ba17.

## 18. Physical witness (Q, final EFRS, blessed harness)

3/3 (wit13a-1/2/3, domains 175/176/177): partition → R3 lease-HELD
112–113× → heal → reconcile (epoch 1 observed) → southern egress
≤3.1 s → detour (y→−1.5) → resume to goal. Runner stale 58–130 ms.
R1 prompt egress ≤3.1 s (physically irreducible inside-at-commit
residuals); R2 clean 0. Ledgers gate_ok all three (655/656/654
ACCEPTs, zero violations). T1 Plain2PC baseline reused (40.4 s
straight-through, never committed); no 2PC rerun/retrofit.

## 19. Gate table

T1.3: G1 PASS, G2 PASS, G3 FAIL(void-workload; superseded),
G4 FAIL(void; superseded), G5 PASS, G6 PASS, G7–G11 superseded by
below. T1.3a: W-HEAL 100/100 PASS, heal-to-commit max 2.06 s PASS,
resource 1.03 PASS, M PASS_WITH_DOCUMENTED_A3_AMENDMENT, N
PASS_WITH_RESTART_AMENDMENT, Q 3/3 PASS.
Combined program verdict: **EFRS_T13A_PASS_WITH_AMENDMENTS**
(A3-control + restart-ordering; both original FAILs retained).
Invalidates nothing outside its scope; T1/T1.1/T1.2 verdicts stand.

## 20. Deviations / bugs (all disclosed)

1. ledger_audit post-freeze tool fixes (row filter, path bug,
   unreadable accounting): read-only audit side; evidence untouched.
2. W-HEAL launcher quoting failure (one empty launch, no evidence).
3. Smoke domains 233/234 over RTPS 232 limit (no records; reran
   228/229).
4. `ros2 topic info -v` live QoS captures missed (containers exit
   first); R by frozen source, B by source + runtime proofs.
5. ACK counts unavailable (D4 gap, carried).
6. Analysis clock-anchor bug (144,457 s → anchored 2.06 s).
7. A3 control inversion (168 ms) → amended → 7792 ms (this doc §17).
8. Coordinator restart UnboundLocalError → amended → [1,2] (§15).
9. T1.3 micro R/B void (permanent-loss confound; superseded, not
   repeated).
10. 2.1 GB RSS level unexplained-but-bounded (flat post-warmup).

## 21. Novelty update

`efrs-t12/docs/EFRS_NOVELTY_BOUNDARY.md` (+T1.2 section): retry,
abort/retry, dedup, idempotence, queue sizing, backpressure, leases,
fencing, 2PC, WAL, reconciliation disclaimed as generic; no
congestion-control novelty (depth-48 recorded as negative result).
Paper claim unchanged: epoch-fenced execution + bounded stale motion
+ mandatory reconciliation. BEST_EFFORT selection explicitly
disclaimed as a contribution (§S).

## 22. Tests

`test_pure.py` 19 proofs green (msgspec/shim/wal/txn/WAL-abort/depth/
source-contracts/ledger-schema/QoS-contracts/sched-util-GST/loss-
branch/old-renewal×2/restart-ordering) locally + frozen container.
`test_qos_ros.py` green in container. Model systematic + fuzz green
(host). Ledger audits green (matrix 483 + N 11 + witness 3 + W-HEAL).

## 23. Commits / push

219b4a7 (T1.2 freeze) → 2680322 (T1.3a runner correction) → 04bc365
(T1.3a interim) → 0053bcb (validity ledger) → e20ba17 (A3 amendment)
→ [restart amendment commit: this commit] → [this report, amended
for the §15 order deviation]. Relay: Mac gh push + host reset --hard
origin/main (verified each step).

## 24. Recommendation

Program complete: STOP. Await lead on publication packaging; no
further experiments authorized by this round. Any follow-up
(transport internals, RSS absolute level, T1-depth questions) needs a
new preregistration.
