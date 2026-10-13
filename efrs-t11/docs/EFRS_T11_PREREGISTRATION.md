# EFRS-T1.1 Preregistration — Eventual-Heal Liveness Repair

Date: 2026-10-13. Frozen BEFORE any T1.1 implementation or experiment.
Parent verdict frozen in `efrs-t1/docs/EFRS_T1_RESEARCH_DECISION.md`
(SAFETY PASS / LIVENESS FAIL / OVERALL FAIL). Conditional claim
boundary in `docs/EFRS_T11_LIVENESS_CONTRACT.md` (same directory).

T1.1 restores progress after transient communication failure/healing
WITHOUT weakening any passed safety property. Forbidden list (§C of
the authorization): majority quorum, skipping unreachable robots,
lease extension for votes, reachable-only commits, MotionFence
weakening, B_real change, stale-epoch renewal, Raft/Paxos/consensus.

## 1. Exact protocol delta (frozen)

### 1.1 Transaction attempt identity (new, additive)

- `txn_id = (candidate_epoch, snapshot_hash, attempt_generation)`,
  wire format `f"tx{epoch}:{hash}:g{gen}"` (string; existing
  `str(txn)` validators keep passing). `gen` starts at 0; a retry of
  the SAME logical update keeps `(epoch, hash)` and increments `gen`.
- Carried on PREPARE, VOTE, ABORT, COMMIT, ACK. A participant never
  applies a message to a different or superseded txn_id; late messages
  from terminal attempts are ignored and logged (counts reported).
- New topics (additive; shim matches them by suffix automatically):
  `TOPICS["abort"] = "/efrs/abort"`, `TOPICS["ack"] = "/efrs/ack"`.
  New constructors `abort_msg(txn, epoch, gen)` and
  `ack_msg(robot, txn, epoch)` with the same validation discipline as
  existing constructors. No existing topic or constructor signature
  changes (COMMIT keeps its fields; its `txn` is now
  generation-qualified).

### 1.2 Coordinator transaction state machine (efrs only)

Per logical epoch, attempts are sequential generations:
`IDLE → WAIT_VOTES(gen) → {COMMITTED | ABORTED}`, then either terminal
or `WAIT_VOTES(gen+1)`. Unchanged rules: propose only `epoch ==
committed+1`; commit iff every reachable robot (seen within frozen
`REACH_MS = 2000 ms`) voted READY; commit decision still WAL-appended
before dissemination (durable linearization point, unchanged).

- `propose(epoch)`: unchanged guard for a NEW epoch; an admin
  re-propose of the SAME pending epoch while no attempt is active
  starts `gen = last_aborted_gen + 1` (idempotent trigger; never
  two active attempts for one epoch).
- During `WAIT_VOTES`: every heartbeat tick (100 ms) republishes
  PREPARE(txn) on the broadcast transport (addressed redelivery is
  impossible on `/efrs/prepare`; agent-side txn dedupe makes
  duplicates idempotent — documented transport-faithful choice, NOT a
  semantic change).
- At the frozen 1500 ms vote deadline with incomplete votes: explicit
  timeout abort — WAL-append `{kind: abort, txn, epoch, gen, hash,
  fence}`, publish `ABORT(txn)` (broadcast; agents match by txn),
  clear `prepared`, record `last_aborted_gen`, set
  `reattempt_at = now + 100 ms`. The coordinator MUST leave the round;
  remaining in WAIT_VOTES past the deadline for any reason is a
  gate failure. Late votes for an aborted txn are ignored + counted.
- Complete votes containing REJECT: ABORT as in T1 (unchanged), but
  reject-abort is TERMINAL for the logical update (a hash/fence
  rejection would re-reject identically; only a new epoch proposal may
  proceed). Timeout-abort (missing votes) auto-reattempts.
- After timeout abort: wait exactly one heartbeat period (100 ms),
  then `WAIT_VOTES(gen+1)` for the SAME `(epoch, hash)` automatically.
  No manual intervention; the runner's 1 Hz propose re-drive remains as
  backup trigger only. Retrying stops when the logical update commits,
  reject-aborts, or the coordinator stops.
- `wal_read_epoch` filters `kind == "commit"` (abort records carry
  `epoch` for identification and must never inflate recovery).

### 1.3 Agent rules (efrs only)

- `prepared` records the full txn (incl. `gen`). Duplicate
  PREPARE(identical txn): return the SAME vote, alter nothing, log.
  PREPARE same epoch with HIGHER gen: supersede (clear old prepared,
  evaluate fresh, log). PREPARE with older gen than prepared: ignore +
  log. Existing REJECT conditions (epoch ≤ committed, fence_seen,
  hash mismatch) unchanged and evaluated before voting.
- `ABORT(txn)`: if prepared.txn matches → clear prepared, log; else
  ignore + log. Never touches committed state.
- `COMMIT(txn)`: existing checks unchanged (epoch/hash/fence), plus:
  same `(epoch, hash)` already applied (any gen) → idempotent no-op +
  log (never a rollback); older gen of an applied epoch → no-op + log;
  `epoch < committed` → reject + log (unchanged). Late COMMIT from a
  superseded attempt for a NEVER-committed epoch evaluates under the
  frozen epoch rules (applies iff checks pass — it carries the same
  authoritative decision).
- ACK: publish `ACK(robot, txn, epoch)` on EVERY commit receipt (new
  or duplicate). Never infer commit state from ACKs (ACKs only prune
  retransmission).
- Contact-sync tightening (§J, safe direction): RENEW NEVER adopts a
  newer epoch. Adoption happens ONLY via COMMIT or reconcile_rep
  (authoritative paths). RENEW extends the lease ONLY when
  `renew.epoch == committed` (adopted currency). A renew carrying a
  NEWER epoch (prepared-but-uncommitted, aborted, future, or simply
  not-yet-learned) triggers a reconcile-pull (reconcile_req; the rep
  installs the authoritative committed epoch) INSTEAD of adopting; it
  extends nothing. A renew for an OLDER (obsolete) epoch is ignored
  entirely, and every ignored renewal is logged. Rationale: the
  coordinator only ever sends committed currency, and every legitimate
  catch-up remains available through COMMIT redrive (§1.4) and
  reconcile-pull; only blind adoption of unverified currency is
  removed, so fault-injected currency can never install. Regression
  tests below. (This supersedes the draft phrasing
  "committed-after-any-adopt", which left the robot-side meaning of
  "uncommitted currency" ambiguous.)

### 1.4 Commit dissemination / ACK recovery

- After a durable COMMIT, the coordinator retransmits `COMMIT(txn)`
  every heartbeat tick until every robot has ACKed (broadcast
  republish + agent dedupe; unacked set pruned by ACKs). Never re-open
  a committed transaction: post-commit votes/aborts for its txn are
  ignored + logged.
- A robot missing COMMIT keeps existing lease-expiry/hold behavior
  (unchanged); after contact heals, existing reconciliation installs
  the authoritative committed epoch (unchanged). The decision existing
  vs the participant having learned it are distinguished in logs
  (commit_log tick vs per-robot ACK tick).

### 1.5 Coordinator restart

WAL records now distinguish ACTIVE (prepared, ephemeral) / ABORTED
(`kind: abort` + txn) / COMMITTED (`kind: commit` + txn). On restart:
durable COMMIT for epoch E exists → `committed = E`, resume COMMIT
dissemination with a fresh unacked set (ACKs rebuilt, never persisted);
durable ABORT(gen g) with no later COMMIT → never resurrect gen g
(a re-proposed same epoch starts at g+1; aborted gens reloaded from
WAL at startup); no durable decision → frozen safe recovery
(re-fence+1, resume, never invent epochs). Never infer COMMIT from
partial votes (unchanged).

## 2. Frozen timing (no tuning)

- Prepare attempt deadline: **1500 ms** (unchanged).
- PREPARE retransmit period: **100 ms** = existing frozen
  heartbeat/contact period (no new tuned constant).
- Post-timeout-abort re-attempt delay: exactly one heartbeat period.
- Recovery timeout (heal-to-commit bound): **10 s**, inherited
  unchanged from the T1 preregistration
  (`recovery_timeout (liveness) = 10 s`); `reconciliation_timeout =
  5 s` likewise inherited. Predates all T1.1 results; derivation in
  the liveness contract (attempt window + abort dissemination + one
  re-attempt cycle + commit dissemination + scheduling allowance).
- Model-tick mapping (model only, frozen): `VOTE_WINDOW_TICKS = 3`,
  `RETRY_DELAY_TICKS = 1`, 1 tick ≈ 1 heartbeat period. The model
  proves LOGIC (no wedge, idempotency, no cross-txn application);
  the 1500 ms bound is proven by ROS experiments, not by the model.

## 3. Model-first plan (§K, gate G1)

Extend `efrs-t11/model/fleet_checker.py` + `EFRS.tla` (frozen T0 model
in `efrs-t0/model/` untouched): txn `(epoch, hash, gen)` on all
transaction messages; coordinator attempt/deadline/reattempt state;
per-tick PREPARE republish to missing voters; timeout abort + ABORT
delivery; auto re-attempt; COMMIT retransmit to non-acked; ACK;
restart disambiguation; tightened contact-sync renewal. Re-run the 9
original T0 systematic schedules + 200-seed fuzz (n=3). New schedules:
first PREPARE dropped; first VOTE dropped; multiple VOTEs dropped;
partial first-attempt PREPARE delivery; heal after first abort; heal
after N aborts; late vote from aborted attempt; late COMMIT from
superseded attempt; coordinator restart between attempts; restart
after durable COMMIT; duplicate PREPARE; duplicate COMMIT; forged
renew for prepared-but-uncommitted epoch (must not adopt/extend);
forged renew for aborted epoch; delayed renew for obsolete epoch.
Liveness monitor: on EVENTUAL_HEAL schedules (heal present, required
participants alive/reachable afterwards, coordinator alive), every
proposed epoch appears in `commit_log` by HORIZON. Required: I1..I7
zero violations + liveness monitor clean. TLA: extend with the attempt
lifecycle (ACTIVE/ABORTED/COMMITTED txn states, idempotent re-vote,
no-cross-txn-application invariant); full-size TLC not required on
explosion, Python n=3 exhaustive/fuzz mandatory. New safety violation
in the model → STOP before ROS.

## 4. Experiment plans

- L (G2): replay the EXACT frozen T1 scale fault trace at 20 robots
  (20% loss schedule + partition groups from `sched-scale20.json`,
  unweakened). First attempt may fail; after heal, automatic
  abort/re-attempt must commit the logical update. Record attempts,
  time-to-abort, heal-to-prepare, heal-to-commit, rejected stale
  messages, HOLD events, stale-motion duration; zero B_real violation.
  No recovery after heal → STOP.
- M (G3/G4): scale-20 with 100 logical updates issued; require 100/100
  eventually committed under the frozen healable mixed-fault workload.
  Retries ≠ new updates. Report attempts, attempts/update,
  retries/update, aborted attempts, prepare/commit/heal-to-commit
  latencies (P50/P95/P99/max), HOLD fraction, network overhead (extra
  txn msgs), coordinator CPU/RSS. Hard safety: zero stale > B_real.
- O (G5): full 3-robot F0–F15 regression on final EFRS; zero I1..I7 /
  bound violations; A3 old-renewal still reproduces the known bug.
- P (G6/G7/G8): frozen 5-robot combos; I2 same-epoch/different-hash +
  mutated-payload rejected; contact-renewal bug stays prevented
  (explicit ROS-fault regression: renew(prepared), renew(aborted),
  renew(obsolete) extend nothing).
- Q (G9): final-EFRS physical witness, 3 reps, blessed amended harness:
  stale robot HOLDs within B_real → heal → reconcile → detour →
  resume; no post-bound straight-through. T1 Plain2PC evidence reused
  as baseline (no 2PC retrofit, §R).

## 5. Mechanical gate (G1..G9 per authorization §S; ANY fail → STOP)

G1 model I1..I7 zero violations (+liveness monitor). G2 13/20 replay
recovers and commits post-heal. G3 scale 100/100 commits. G4 zero
stale >1300 ms at scale. G5 3-robot regression clean. G6 5-robot clean
with post-heal progress. G7 I2 rejected. G8 renewal-bug prevented. G9
witness 3/3 bounded HOLD→reconcile→detour→resume. Forbidden escapes:
deadline lengthening, commit-semantics weakening, quorum change, lease
extension, consensus addition, hiding stalled updates.

## 6. Deliverables (§U)

`docs/EFRS_T11_PREREGISTRATION.md` (this file),
`reports/EFRS_T11_REPORT.md`, `reports/efrs_t11_results.json`
(machine-readable gate table + distributions). Report returns the 19
items in authorization §U verbatim. Success wording frozen (§T):
"EFRS maintains bounded stale-rule execution under the modeled
failures, and restores update progress after eventual network healing
through idempotent transaction recovery." Banned: "non-blocking atomic
commit under arbitrary partitions".
