# EFRS Preliminary Theorem Statement (T0)

Status: PRELIMINARY. What follows is established by exhaustive checking
at n=3 within documented bounds (evidence cited); the unbounded proof
is future work and is NOT claimed.

## Definitions

- Fleet of n robots + coordinator role; snapshot `{epoch, hash,
  hard_rules}`; lease L; bound BOUND=L.
- Motion gate: execute(required_epoch) allowed iff
  `local_committed_epoch == required_epoch`, lease live, reconciled.
- Contact-sync: every coordinator message carries current
  (epoch, fence); renewal extends leases only at adopted currency.

## Theorem (bounded, checked)

For n=3, epochs {0,1,2}, horizon 12, lease 5, over the 9-schedule x
2-plan systematic set plus 400 randomized fault schedules per protocol
covering {delay, drop, duplicate, reorder, robot crash/restart,
coordinator crash/restart, partition/heal, late commit, stale command,
reconnect}:

(a) plain 2PC admits stale-rule-window traces (S1/S6), a late-commit
    rollback trace violating I1 (S7), and superseded-epoch post-restart
    traces violating I5/I6 (S8);
(b) best-effort broadcast admits I3/I5/I6/I7 violations on the same
    classes plus unbounded staleness;
(c) EFRS admits NO trace violating any of I1..I7;
(d) every EFRS stale-epoch execution lies within BOUND ticks of the
    superseding commit (measured max 1 tick vs BOUND 5).

Evidence: `model/fleet_checker_results.txt` (exit-clean),
`model/EFRS.tla` + TLC (8,472 states, no error, small instance).

## Explicitly NOT established

- Unbounded-horizon / arbitrary-n proof (needs inductive invariant +
  full TLC/TLA+ proof or Ivy-style reasoning; scoped for later).
- Adversarial message-content faults (outside the closed fault list;
  I2 vacuous accordingly).
- Performance claims of any kind (T0 forbids optimization talk).
- That Raft/Paxos-equivalent consensus is unnecessary: EFRS uses
  quorum READY + fencing as infrastructure, exactly as briefed.

## What would falsify this statement

A single EFRS trace violating I1..I7 inside the stated bounds. The
harness is deterministic and re-runnable (`python3
model/fleet_checker.py`); any such trace must be treated as a
T0-blocking bug, not as noise.
