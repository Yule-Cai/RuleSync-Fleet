# EFRS-P0 Protocol Reconstruction (from final implementation)

Sources read (not docs-first): `efrs-t13a/efrs_ros2/coordinator/
coordinator.py` (413 lines), `robot_agent/robot_agent.py` (367),
`motion_fence/motion_fence.py` (184), `wal.py`, `msgspec.py`,
`shim.py`, `rosutil.py`. Compared against `efrs-t0/docs/
EFRS_T0_CONTRACT.md`, `efrs-t1/docs/EFRS_T1_REPORT.md`,
`EFRS_T1_RESEARCH_DECISION.md`, I1–I7, B_real=1300 ms.

## 1. Coordinator state machine (actual)

Persistent: `epoch` (max durable commit), `fence` (+1 on every
restart), aborted `(epoch,gen)` set, reject-terminal epochs.
Volatile per attempt: `prepared{epoch,hash,fence,txn,gen}`, `votes{}`
(robot→READY|REJECT), `vote_deadline` (now+1500 ms),
`pending` ( rebuilds to `committed+1` on restart if proposed),
`reattempt_at`, `acked{}` (evidence only).

Transitions: propose(epoch) [guard: epoch==durable+1; EFRS: one active
attempt/epoch; reject-terminal refused; re-propose bumps gen past
aborted] → begin_attempt publishes ONE PREPARE → votes accrue →
decide() on each vote and on baseline timeout: commit iff
`set(votes) ⊇ set(reach)` with all READY, where
`reach = {robots seen (state msg) within REACH_MS=2000 ms}`.
Commit = `wal_commit` THEN publish COMMIT (durable first).
Non-unanimous reachable votes → EFRS reject_abort (terminal for the
epoch) / timeout_abort (re-attempt in ~100 ms with fresh gen);
baselines clear and retry by timeout-decide.
Restart: fence+1, ONE COMMIT replay of the durable epoch (post-helper
amendment), pending rebuild to committed+1, never invent, never
resurrect aborted/rejected. Heartbeat publishes RENEW(epoch,fence)
every 100 ms (EFRS only). Reconcile requests answered with current
(epoch,hash,fence,rules). ACKs counted only.

## 2. Durable commit linearization point

`wal_commit()` append (fsync) in `decide()`, BEFORE the COMMIT
publish. Restart recovery reads max kind=="commit" epoch (abort
records filtered). Single coordinator ⇒ WAL order is the commit
order; no consensus. Crash between WAL-append and publish is closed
by the single restart replay + reconcile-pull.

## 3. Epoch and snapshot-hash binding

Epoch e carries rules payload `_re(e)` and `snap_hash=canonical_
rules_hash` (sha256/16 of canonical JSON). PREPARE/COMMIT carry
(epoch,hash,fence,rules); agents `verify_rules` at PREPARE-vote,
COMMIT-apply, and reconcile_rep-apply; mismatch ⇒ REJECT vote /
ignore. I2 enforcement point = adoption-time verification (not a
background invariant scan).

## 4. Transaction attempt and generation semantics

`txn = tx{epoch}:{hash}:g{gen}`. Same-epoch re-propose ⇒ fresh gen
(skipping aborted). Agent: identical txn ⇒ idempotent no-revote
(T1.2: emits NOTHING); older gen of same (epoch,hash) ⇒ ignore;
newer ⇒ supersede prepared. ABORT(txn) clears ONLY matching prepared
(never committed). COMMIT with same (epoch,hash) as committed ⇒
idempotent no-op + ACK (never rollback). COMMIT with same epoch but
different hash ⇒ rejected (I1). Late votes for non-active txn counted
and ignored. One vote, one ACK per robot per txn.

## 5. Reachable-participant vs required-participant logic

The protocol does NOT require all-configured unanimity. It commits
over the OBSERVED REACHABLE SET (state seen ≤2000 ms) unanimously.
A robot silent >2 s is excluded from the threshold; its safety is
carried ENTIRELY by lease expiry (lease 1000 ms < 2000 ms window, so
excluded robots are already holding). No majority quorum, no fixed
quorum at all; the "quorum READY" language of T0 is implemented as
reachable-unanimity. Unreachable-but-voted edge: votes only count
from currently-reachable robots at decide() time.

## 6. Lease expiry and contact-sync

COMMIT grants lease_ms=1000 (EFRS; baselines get 10^30/10^12 =
never). Agent extends its deadline ONLY on adopted-currency contact:
same-epoch RENEW (or COMMIT/reconcile_rep). Newer-epoch RENEW ⇒
reconcile-pull, NO adoption, NO extension. Obsolete-epoch RENEW ⇒
ignored. Restart loads (committed,hash,fence_seen) and starts
UNRECONCILED (lease_deadline 0 ⇒ holding). `--old-renewal` preserves
the T0 bug (extend-without-adopt) as the A3 control; `--no-lease-
expiry` disables expiry (A2-style control).

## 7. MotionFence authorization checks (exact, conjunctive)

Per command at decision instant t (steady clock), EXECUTE iff ALL:
(1) required_epoch == agent committed epoch; (2) required_hash ==
agent hash; (3) t ≤ lease_deadline_ns (unless --ignore-lease);
(4) agent reconciled; (5) agent NOT holding. Else REJECTED
(epoch/hash mismatch, no-agent-state) or HELD (lease-expired,
unreconciled, agent-holding) + safe-stop event. Every decision
ledgered (fsync before ACCEPT evidenced). Baselines/passthrough
EXECUTE everything as "no-gate" (defect under test, comparable
schema). Fence reads agent state via /efrs/state @5 Hz + guard 50 ms
budget inside B_real.

## 8. Robot restart and coordinator restart

Robot: durable (committed,hash,fence_seen) reloaded; starts
UNRECONCILED ⇒ holding ⇒ fence HELDs everything; re-requests
reconcile @~1 Hz; reconcile_rep with epoch ≥ committed installs
(epoch,hash), ratchets fence_seen, extends lease, reconciled=true,
holding=false. Never rolls back (I1); never adopts via RENEW.
Coordinator: WAL max-epoch + fence+1; one COMMIT replay; pending
rebuild; re-attempt loop resumes. Fence_seen ratchet on robots
rejects pre-restart commits (fence < seen) at PREPARE-vote, COMMIT,
and RENEW.

## 9. Reconciliation prerequisites

Motion resumes only after: reconcile_rep applied (or same-currency
RENEW for a merely-healed non-restarted robot) AND lease live AND
holding==false (holding = unreconciled OR lease-expired, recomputed
@5 Hz). Partition heal alone authorizes nothing (T0 S1/S2 class).

## 10. Safe HOLD transition

HOLD is entered locally and unilaterally: lease expiry or
unreconciled status flips `holding` in the 5 Hz state tick; the
fence's next decision HELDs with reason; a safe-stop/HOLD event is
emitted. No coordinator interaction required (fail-safe default).
237 lease-HOLDs over 265 s of T1 scale-20 degradation with zero stale
motion is the standing demonstration.

## 11. Recovery after eventual communication healing

Healed robots receive RENEWs (same currency ⇒ extend + reconcile if
needed; newer ⇒ pull) and/or missed COMMITs (adopt if fence/hash
pass) and/or reconcile_rep on request. Coordinator auto-reattempts
pending epoch+1 gens at ~100 ms cadence until commit (W-HEAL 100/100,
heal-to-commit ≤2.06 s). No COMMIT redrive loop (removed T1.2);
catch-up is pull-side.

## 12. Comparison: formal vs implementation (gaps, explicit)

G1. T0 "re-fence (token+1) through a quorum": no quorum mechanism
exists (single coordinator, quorum forbidden by T1.1 authorization).
Implemented as local fence+1 with WAL monotonicity + robot-side max-
tracking. Safe under single-coordinator assumption; the quorum
wording is unimplemented. HARMLESS gap (assumption-narrowing).
G2. T0 "(quorum READY)" vs implementation reachable-unanimity with
2 s window. Excluded-robot safety rests solely on lease expiry (I4).
Documentary tension with T1.1's "no reachable-only commits" phrasing
(read: no threshold-weakening; frozen rule kept). BEHAVIORAL fact
relevant to §F: commit does NOT imply all robots adopted;
reconciliation is lazy/pull. No evidence of harm (I4 holds everywhere
measured); formal statement weaker than code reality in one direction
(code commits in strictly more situations than all-required
unanimity).
G3. Ticks→milliseconds: T0 BOUND=L=5 ticks; ROS B_real=1000+50+250 ms
(lease+guard+jitter). The 50 ms fence-scheduling and 250 ms
in-flight-drain budgets are engineering allocations, measured
consistent (max 552 ms cell) but never stress-proven near the bound.
Positive control (A3, 7792 ms) proves the metric detects violation.
G4. Test/ablation escape hatches IN production code (`--passthrough`,
`--ignore-lease`, `--no-lease-expiry`, `--old-renewal`): absent from
the formal model; used only as documented positive controls. Formal
coverage is of the default-flag configuration.
G5. Single-host experiments: all ROS processes share one steady clock
domain; cross-machine clock behavior untested. mitigates: lease
expiry is PER-ROBOT LOCAL (no inter-robot sync needed for safety);
timing measurements (stale_ms) assume local monotonicity only.
G6. Vote timeout 1500 ms and REACH_MS 2000 ms are harness/stability
choices, not gates; liveness (not safety) depends on them.
