# EFRS-T0 Protocol Contract (frozen for fault exploration)

EFRS = Epoch-Fenced Rule Sync. Fleet extension of the single-robot
RuleSync durable path (RuleSpec + PREPARE/(READY|REJECT|TIMEOUT) +
durable WAL COMMIT + certificate-bound application + convergence on
`(epoch, snapshot_hash)`). T0 covers protocol definition, formal model,
and exhaustive fault exploration ONLY. No performance optimization,
no Gazebo, no LLM, no large implementation.

## 1. Fleet model

- Robots `R = {r1..rn}`, `3 <= n <= 5` (checker default `n = 3`).
- One coordinator role `C` (crashable; restart must recover, never invent).
- Rule snapshot: `{epoch: nat, hash: H(hard_rules), hard_rules: set}`.
  `hash` uniquely binds the hard-rule set to the epoch (I2).
- No reliable broadcast assumption. All messages can suffer delay, drop,
  duplicate, reorder unless a mechanism explicitly closes it.

## 2. Lease and fence

- Every commit grant carries `lease = L` ticks (frozen `L = 5` in T0).
- A robot's committed epoch is *actionable* only while its lease is
  unexpired on its local clock. Expiry forces safe-hold (I4).
- Fence: the coordinator holds a monotonic `fence_token`, issued at
  commit time. A restarted coordinator must re-fence (token+1) through a
  quorum before committing; commits under an old token are rejected by
  robots. This closes stale-coordinator commits after crash/restart.

## 3. Motion gate (all protocols carry required_epoch; only EFRS enforces)

Every motion command carries `required_epoch`. A robot may execute it
iff ALL hold at execution instant:

    local_committed_epoch == required_epoch   (I3)
    AND lease unexpired                        (I4)
    AND not (reconnecting and not yet reconciled)  (I7)

otherwise it must safe-hold (zero motion, latched alarm flag).

## 4. State machines

### 4.1 Robot (EFRS)

States: `IDLE --PREPARE--> PREPARED --COMMIT--> COMMITTED --(lease
expiry)--> HOLD --(reconcile)--> COMMITTED`; `CRASHED` from any state
(loss of volatile lease timer; stable storage keeps committed epoch +
hash); restart lands in `RECONCILING` (no motion) until reconcile
completes (fetch coordinator epoch/hash, verify, catch up or roll
forward; never roll back, I1; never resurrect a superseded epoch, I6).

### 4.2 Coordinator (EFRS)

States: `STABLE --propose--> PREPARING --(quorum READY)--> COMMITTING
--(durable write + grants)--> STABLE(new epoch)`; abort path returns
to `STABLE(old epoch)`; crash loses volatile round state; restart
recovers last durable epoch, re-fences, reconciles robots before new
proposals.

### 4.3 Baseline degradations (same fault model, fewer mechanisms)

- BEST-EFFORT BROADCAST: no PREPARE/votes, no lease, no fence, no gate
  enforcement. COMMIT applied on receipt. Reconnect does not reconcile.
- PLAIN 2PC: single-robot 2PC extended to n robots (PREPARE, votes,
  COMMIT on all-READY, ABORT otherwise). No lease/fence/gate/reconcile.
  A robot that misses COMMIT (partition/crash) keeps its old epoch with
  no expiry — the stale-rule window under test.

## 5. Fault model (closed list, applied as nondeterministic choices)

Message delay / drop / duplicate / reorder; robot crash/restart;
coordinator crash/restart; network partition (and heal); late commit
(COMMIT delivered after newer state exists); stale command (motion with
old required_epoch arriving late); robot reconnect. Duplicates are
idempotent by (txn_id/epoch/hash) matching; reorder is absorbed by the
same match plus epoch monotonicity.

## 6. Invariants under check (I1..I7)

- I1: robot committed_epoch never decreases.
- I2: equal epochs imply equal hashes fleet-wide.
- I3: every executed motion has required_epoch == local committed epoch.
- I4: a robot out of contact past its lease performs no motion.
- I5: after a fleet hard-rule commit at tick T, stale-epoch execution
  ends by T + BOUND, with BOUND = L (lease ticks) preregistered.
- I6: restart never restores a superseded epoch as actionable without
  reconcile; no motion until reconciled.
- I7: reconnect completes reconcile before motion resumes.

## 7. T0 exit rule

T0 must exhibit the plain-2PC stale-rule-window counterexample
(committed robots on new rules while a partitioned robot keeps
executing old rules with no bound). If EFRS shows NO violation of
I1..I7 on the same fault schedules where a baseline violates, T0
passes to ROS2 fault-injection. If EFRS fails to eliminate the
counterexample class: STOP.
