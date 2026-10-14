# EFRS-T1.2 Interim Report — STOP at W-HEAL (G3 74/100 FAIL, no tuning)

Date: 2026-10-13/14. Status: STOPPED per §R (ANY fail → STOP). No
deadlines/queues/timeouts/leases/quorums changed after results, no
re-runs, no workload weakening. G7–G10 NOT RUN. T1.1 O/P diagnostics
were folded per §L (their scenarios live in the T1.2 regression
scheds, staged but unexecuted).

## 1. T1.1 closeout / adjudication (lead rulings implemented)

T1.1 STOP stands (12/100). Permanent-loss tail reclassified
INCONCLUSIVE FOR EVENTUAL-HEAL (loss_random without `until` stacked
to ~91% — no valid falsification of the conditional claim). The 28
sustained-expiry events: UNRESOLVED/INSUFFICIENT-OBSERVABILITY
(neither proven violations nor successes). Closeout frozen in
`efrs-t11/docs/EFRS_T11_FINAL_RESEARCH_DECISION.md`. T1.1 trace
preserved as sustained-loss safety stress (reused as W-SUSTAINED).

## 2. Exact T1.2 protocol delta (frozen 219b4a7, runner cd575e79)

- One PREPARE per attempt (heartbeat retransmit DELETED; source
  contract: exactly 2 PREPARE sites — begin_attempt + frozen baseline
  path; heartbeat contains none — AST-tested).
- One VOTE per robot per txn (duplicates recognized, emit nothing).
- One COMMIT per durable decision (+ ONE restart replay); ACK-driven
  redrive DELETED; catch-up via reconcile-pull only.
- One ACK per robot per txn (evidence only).
- CONTROL_DEPTH = max(32, 2N+8) on PREPARE/VOTE/ABORT/COMMIT/ACK
  pubs+subs (N=3→32, 20→48); telemetry stays 10.
- Local fence ledger (JSONL, fsync/decision, F1 schema; fence_seen
  wired through state_msg additive field).
- Sequential logical issue (epochs 1..100, e+1 after e commits, no
  queue); gen-scoped `drop_gen_votes` fault kind + `txn_gen` shim
  match (K replay only).
- Unchanged: thresholds, REACH_MS, B_real, lease/heartbeat, WAL
  linearization, contact-sync tightening, A3 path, unanimity.

## 3. Queue-depth derivation (§E, frozen)

One burst ≈ N votes + N ACKs + margin ⇒ max(32, 2N+8). Fixed BEFORE
outcomes; function-tested for 3/5/20. (Post-result analysis in §20
revisits this choice as the prime collapse suspect — recorded, NOT
changed.)

## 4. Ledger schema (§F, frozen)

monotonic_ns, robot_id, local_committed_epoch/hash,
lease_deadline_monotonic_ns, required_epoch/hash, cmd_id,
decision ACCEPT/REJECT, reject_reason, reconciled, holding,
fence_seen (nullable). Write+fsync BEFORE ACCEPT publication.
F1 audit tool: `fault_harness/ledger_audit.py` (fixed twice
post-freeze for tool bugs — wrong row filter, str.path bug — both
read-only audit-side, disclosed here; no ROS re-runs needed).

## 5. Model results (G1 PASS)

Host record: T0-9 rerun clean; 17/17 systematic zero I1–I7 with
commits (K1–K3 now via abort→reattempt; K5/G-f multi-abort cycles;
G-a pull catch-up; G-b/G-c hold semantics); G-c + J1–J3 exact
assertions PASS; 200-seed fuzz efrs clean; baselines reproduce T0
counterexamples. TLA: T1.1 extension carried over (single delivery
collapses identically in the abstraction; traffic rules enforced by
§P source contracts instead). T1.1 TLC outcome cited (57M states, no
violations, OOM — allowed subordinate outcome).

## 6. Deterministic 13/20 replay (G2 PASS)

20 robots, gen-0 votes of R14–R20 dropped (gen-scoped, no timing
dependence). First attempt: exactly R1–R13 (13/20) → TIMEOUT-ABORT
→ auto gen-1 → commit(1,g1), no manual re-propose, stale 4.7 ms.
Ledger audit on K13: gate_ok (0/0/0/0, 0 unverifiable).

## 7. W-SUSTAINED (G5 PASS, G6-shape PASS)

Exact T1 trace (byte-identical sched): 2/100 commits (descriptive,
allowed), 51 aborts / 48 reattempts firing throughout, stale_max
150.0 ms. Ledger: 20/20 ledgers, 1991 rows, 1632 ACCEPTs,
accepted_after_expiry = epoch_mismatch = hash_mismatch =
reconciling = 0, 0 unverifiable. Central-channel counters
(auth 303, invalid_lease 21, unverifiable 282) are evidence-drop
artifacts under 91% ambient loss (lead-adjudicated class).

## 8–11. W-HEAL (G3 FAIL; G4 UNMEASURED; O metrics as observed)

Sequential 100 updates, GST=248.02, cap 600 s: **74/100 committed,
76 issued**. Epochs 1–74 committed in the first 5.1 s (~70 ms each);
then zero commits for 595 s; 51 aborts (first 8.0 s, last 587.8 s).
- Attempts/update: 1.0 for epochs 1–74 (no retries needed pre-loss).
- Message counts (node logs): 741 PREPARE broadcasts, 74 COMMIT
  broadcasts (+1 restart-class replay: none needed), 1641 votes
  received, 0 redrives (deleted ✓), 0 retransmits (deleted ✓).
  Per committed update: ~10 PREPARE / ~22 votes-received / 1 COMMIT.
  ACKs uncounted (D4 evidence-only; no coordinator log line —
  instrumentation gap, disclosed).
- Heal-to-commit: UNMEASURED (no post-GST recovery occurred).
  Stale max 364.9 ms. HOLD rejections 20,737 (fences held throughout).
- Resources: CPU sustained ~160–199%, RSS 2.1 GB (vs T1 same fleet
  30%/~400 MB). Evidence starvation 8:1 (7339/60000 states; commit
  events missing for epochs 10–69 — dropped before recording).

## 12. Local safety-ledger results (G6 PASS)

W-HEAL: 20/20 ledgers, 29,968 rows, 6,059 ACCEPTs, all four F1
counters 0, 0 unverifiable (`gate_ok: true`). The ledger (complete,
local) overrules the degraded central channel (27 sustained-expiry
flags + 525 unverifiable there): per §F, missing central telemetry
is not safety evidence when the ledger exists. No ACCEPT violated
expiry/epoch/hash/reconcile rules across 6,059 decisions.

## 13–18. Regressions / witness / I2 / A3: NOT RUN (STOP)

Scheds staged byte-identical (`t12_3robot` 51 files, `t12_5robot`
13 files) + batch script `run_t12_matrix.sh`; never executed per §R.

## 19. Gate table (G1–G10)

G1 PASS. G2 PASS. G3 FAIL (74/100). G4 UNMEASURED (prerequisite
recovery absent; stale bound itself holds). G5 PASS. G6 PASS.
G7–G10 NOT RUN. Machine table: `efrs_t12_results.json`. Verdict:
**EFRS_T12_FAIL** (mechanical). No publication decision made here.

## 20. Deviations / bugs (all disclosed, none silently fixed)

1. `ledger_audit.py` post-freeze tool fixes (row filter, path bug,
   unreadable-ledger accounting): read-only audit side; evidence
   (frozen-code ledgers) untouched; K13/SUSTAINED/W-HEAL audits
   re-run on existing records.
2. W-HEAL launcher quoting failure (one empty launch, no evidence
   produced) → script-file launcher; no science impact.
3. Smoke domains 233/234 exceeded the 232 RTPS limit (container
   signature: zero records) → reran on 228/229; failed containers
   left no records (nothing cited).
4. T1.2 PRIME FINDING (design flaw, NOT patched): depth-48 RELIABLE
   many-to-one vote path collapses at first sustained loss (votes
   1613 in minute 0 → ~0 after; PREPARE path still delivered gen-169;
   CPU/RSS 160%/2.1 GB). T1.1 at depth 10 survived the same phase.
   Fixing in either direction changes frozen values → STOP, not tuning.
5. Sequential-issue + abort-wipes-quorum dynamics: under sustained
   loss, each 1.5 s abort discards partial quorums; combined with (4),
   no window completes. Mechanism certain; depth-causality strongly
   correlated (single variable changed on that path); DDS-level proof
   beyond current instrumentation.
6. ACK instrumentation gap (counts unavailable) — §O metric missing.

## 21. Novelty-boundary update

Per §S (to be committed with this report if the file exists in
scope): retry/abort/dedup/idempotence/queue-sizing/backpressure/
leases/fencing/2PC/WAL/reconciliation explicitly disclaimed as
generic mechanisms; paper claim stays epoch-fenced execution with
bounded stale motion + mandatory reconciliation; no
congestion-control novelty claimed.

## 22. Tests

`test_pure.py` (12 proofs: msgspec/shim/wal/txn/WAL-abort/depth
mapping/source contracts/ledger schema) green locally + in frozen
container pre-freeze. Model systematic + fuzz green on host.
Ledger audits green (K13, SUSTAINED, W-HEAL).

## 23. Commits / push

Freeze-1 `219b4a7` (contract/model/impl/ledger/W-scheds/tests).
This report + results.json → commit + Mac-relay push + host sync.

## 24. Recommendation

STOP stands. Await lead on: (a) whether the vote-path collapse
mechanism warrants a T1.3 with revised queue/transport treatment
(new prereg required; NOTE §R currently forbids depth changes in
either direction); (b) W-HEAL workload validity under sequential
issue (74 commits in 5.1 s shows the pre-loss phase needs no
liveness help — the workload's discriminative power sits entirely
in loss phases where single-shot unanimity needs near-perfect
windows); (c) G4 adjudication (recovery timeout never exercised);
(d) whether M/N/Q diagnostics may run for information.
