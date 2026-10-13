# EFRS-T1.1 Interim Report — STOP at L/M (G3 FAIL, no tuning)

Date: 2026-10-13. Status: STOPPED per preregistration §S (mechanical
gate: ANY fail → STOP). No deadlines lengthened, no quorum changed, no
leases extended, no consensus added, no workload weakened, no re-runs.
All §U return items answered below to the extent reachable before STOP;
items 10–14 (regressions, witness) NOT RUN.

## 1. Exact protocol delta (implemented, frozen a565aac, runner 6c6b674f)

- `txn_id = tx{epoch}:{hash}:g{gen}` on PREPARE/VOTE/ABORT/COMMIT/ACK
  (msgspec builders + validators + `parse_txn_id`; malformed never
  crashes a node).
- Coordinator: one active attempt per epoch; PREPARE republish every
  heartbeat (100 ms) on broadcast (agents dedupe); explicit
  timeout-abort at frozen 1500 ms (durable WAL `abort/timeout` record,
  ABORT broadcast, MUST leave round); auto re-attempt exactly one
  heartbeat later with gen+1 (never resurrects); REJECT-abort terminal
  for the epoch; COMMIT redrive every heartbeat until all ACK;
  restart resumes COMMIT dissemination / rebuilds pending from WAL
  (reject-terminal epochs refused).
- Agent: idempotent same-txn re-vote; gen supersede/ignore rules;
  ABORT clears only matching prepared; same-(epoch,hash) COMMIT is a
  no-op + ACK; conflicting same-epoch hash rejected; ACK on every
  COMMIT receipt; RENEW never adopts (reconcile-pull on newer epoch,
  lease extends only for adopted currency, obsolete ignored);
  `--old-renewal` preserves the exact pre-T1.1 path as A3 control.
- Runner: additive `/efrs/txn_event` subscription persisted as
  `record["txn_events"]`; motion/state/commit schemas unchanged
  (frozen analyzer runs unmodified on T1.1 records).

## 2. Model result (G1 PASS, host record /tmp/t11_model2.log)

- T0 9 systematic schedules rerun: EFRS 0 violations (identical to T0);
  baselines reproduce T0 counterexamples bit-for-bit (I1/I3/I5/I6/I7).
- New K1–K10: 0 violations + liveness commits, incl. genuine cycles —
  K3 (aborts=1, gen=1), K4 total-isolation (aborts=1, gen=1, commit
  post-heal), K5 (aborts=2, gen=2, commit post-heal), K8 restart
  (gen advances, no resurrection), K7 late-COMMIT (no rollback).
- §J micro-tests 3/3 PASS with exact end-state assertions (prepared
  currency ignored; dead-coordinator renew extends nothing;
  obsolete renew extends nothing).
- 200-seed fuzz: efrs clean; baselines hit only expected kinds.
- TLA: attempt layer appended to EFRS.tla (NoCrossTxn / AttemptLeaves
  liveness under WF / GenBounded) + EFRS_t11.cfg; TLC hit state
  explosion (57M+ states, still running at write time) — allowed
  outcome per prereg; Python n=3 exhaustive/fuzz is the mandatory gate.

## 3–4. Retry/abort semantics + frozen timing

Per prereg §1–§2 (1500 ms window; 100 ms heartbeat retransmit;
+100 ms re-attempt delay; 10 s recovery timeout inherited). Live
micro-verification (3-robot, frozen code): clean F0smoke (2 epochs,
gen 0, stale 44 ms) and abort test (loss_burst on VOTEs):
attempt(1,g0) → abort → reattempt → commit(1,g1) → epoch 2 clean,
stale 23.8 ms. Records: `experiments/smoke/`.

## 5–9. Scale replay (G2 FAIL strict, G3 FAIL, G4 PASS)

Workload: byte-identical T1 `sched-scale20.json` (100 proposes,
20 robots, vote 1500 ms), frozen T1.1 stack, domain 161.
- Commits: **12/100 distinct epochs** (1–12, incl. epoch 5 via an
  abort→reattempt cycle). 46 abort events recorded (138 in
  coordinator.log — evidence channel itself drops 2/3 under load),
  37 reattempts, 699 commit_redrives recorded.
- Stall: epoch 13 attempted gens 119–134 then the run ended; epochs
  14–100 never attempted (propose gate epoch == committed+1).
- Safety on the measurable part: stale_max **464.2 ms** (< B_real),
  0 mismatches, 0 rollbacks, 0 unreconciled, 425 fence rejections.
  421 race-bounded auth accepts (393 unverifiable — no contemporaneous
  agent snapshot under evidence-channel drops); 28 sustained-expiry
  EXECUTED under 36–91% ambient loss cannot be individually
  exonerated from this record (asymmetric-drop artifact likely;
  reported, not hidden).
- Root causes (evidence-backed, §U-16): (a) `loss_random` never
  clears — 11 stacked permanent losses drive ambient 20%→91%, so the
  tail permanently violates EVENTUAL_HEAL; no unanimity protocol can
  commit at 91% loss. (b) Redrive-until-all-acked never terminates
  under sustained loss (epochs redriven 139–180x recorded) → growing
  broadcast flood. (c) 10 Hz retransmit to non-shrinking missing sets
  + per-duplicate re-votes saturate depth-10 queues (coordinator saw
  1536 votes/274 s; agents kept voting). (d) Each timeout-abort wipes
  the accumulated partial quorum, so no 1.5 s window ever completes.
- The T1 13/20 first-round phenomenon did NOT recur (epoch 1
  committed clean — run-to-run spawn/discovery timing variance);
  G2 marked FAIL on strict reading.

## 10–14. Regressions and witness: NOT RUN (STOP)

3-robot F0–F15, A3, 5-robot/I2, contact-sync ROS faults, physical
witness — scheds staged byte-identical under
`experiments/t11_3robot|t11_5robot/` but never executed, per §S.

## 15. Gates

G1 PASS. G2 FAIL (strict). G3 FAIL (12/100). G4 PASS (464.2 ms).
G5–G9 NOT RUN. Verdict: STOP. Machine table:
`reports/efrs_t11_results.json`.

## 16–17. Deviations/bugs + novelty boundary

- No frozen timing/parameter changed at any point; no re-runs.
- Two design flaws exposed (not patched, per STOP): never-ending
  COMMIT redrive under sustained loss; fixed-rate retransmit flooding
  depth-10 queues. Any rate adaptation, ack-quorum, or redrive cap
  changes frozen semantics → requires a lead decision, not an
  implementation tweak.
- Workload-validity question for the lead (§M vs EVENTUAL_HEAL):
  the T1 scale trace's permanent-loss tail (to 91%) is unsatisfiable
  for 100/100 under ANY unanimity threshold — M on this exact trace
  tests impossibility, not the repair.
- Novelty: no claim of novel retries/recovery (per §R); the repair
  attempt is recorded as conditional-liveness engineering with a
  negative result at scale.

## 18–19. Commits/push + recommendation

- Freeze `a565aac` (implementation + model + docs). This report +
  results.json → commit below, push via Mac relay, host synced.
- RECOMMENDATION: STOP stands. Await lead on (a) M-workload validity
  under permanent loss, (b) whether redrive/retransmit rates may be
  revisited (new prereg required), (c) adjudication of the 28
  sustained-expiry executions, (d) whether O/P/Q diagnostics may run
  for information (not gate credit).
