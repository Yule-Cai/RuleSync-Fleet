# EFRS-T0 Baseline Comparison (executed, not asserted)

Engine: `model/fleet_checker.py` (9 systematic schedules x honest/stale
plans + 200-seed x 2-plan fuzz per protocol; n=3, horizon=12, lease=5).
Full raw output: `model/fleet_checker_results.txt`. TLA+ gate model:
`model/EFRS.tla` (+TLC result below).

## Violation matrix (systematic schedules)

| sched | fault pattern | broadcast | plain 2PC | EFRS |
|---|---|---|---|---|
| S0 | clean, epochs 1+2 | clean | clean | clean |
| S1 | partition r3 t2..8, commit e1 | I7 | I7 | clean |
| S2 | S1 + COMMITs dropped | I7 | I7 | clean |
| S3 | r3 crash/restart across commit | clean | clean | clean |
| S4 | coordinator crash/restart | clean | clean | clean |
| S5 | stale motion commands | I3 x33 | I3 x27 | clean |
| S6 | long partition, commits inside | I5 x4 | I5 x2 | clean |
| S7 | late COMMIT (+6 ticks) | clean | **I1 x3 (rollback)** | clean |
| S8 | crash + dropped COMMITs + restart | I5+I6 | I5+I6 | clean |

Fuzz (400 traces/protocol): broadcast {I3,I5,I7}, 2PC {I1,I3,I5,I7},
EFRS {} (zero violations).

## Headline counterexample: plain-2PC stale-rule window (S1 trace)

```text
t=5 C COMMITS epoch 1 (durable)
t=6 R1 applies 2PC epoch 1 / R2 applies 2PC epoch 1
t=6 R1 executes (req 1, local 1)   <- new rules live
t=6 R3 executes (req 0, local 0)   <- partitioned, old rules, no bound
t=7 R1 executes (req 1, local 1)
t=7 R3 executes (req 0, local 0)   <- stale-rule window
t=8 HEAL / R3 applies epoch 1      <- closed here ONLY by luck of heal
```

Unbounded variant (S6, no heal): stale executions reach 9 ticks
(broadcast) / 7 ticks (2PC) past commit vs BOUND=5; EFRS max = 1.

## Same fault model under EFRS

Identical schedules: R3's lease expires without renewal → safe-hold at
t=7,8 (S1 shows EFRS stale execs only at t=5,6, inside the lease);
late COMMITs rejected by certificate/fence (S7 clean); restarts hold
unreconciled until reconcile (S8 clean); stale commands rejected by the
motion gate (S5 clean); post-heal motions follow reconcile (S1/S2 clean).

## Honest coverage statement

- I2 is vacuous in this model: no fault in the closed list mutates
  message content, so epoch->hash consistency holds by construction in
  all three protocols. It is checked (and passes), not proven in an
  adversarial-content sense.
- I4/I6/I7 for EFRS hold structurally (hold/reconcile paths) and are
  exercised by S1/S3/S6/S8 plus fuzz; the checker confirms zero
  violating traces rather than proving absence in an unbounded model.
- State space: exhaustive over the 9-schedule x 2-plan systematic set
  and 400 randomized schedules per protocol at n=3. n=4/5 and longer
  horizons are NOT covered in T0 (deferred to ROS2 fault-injection).

## TLA+ gate model (machine-checked)

`model/EFRS.tla` + `model/EFRScfg_small.cfg` (2 robots, MaxEpoch 1,
Lease 3, Horizon 5): TLC explored 8,472 distinct states, **no error**
— GateLogged holds and the spec is deadlock-free. Full-size TLC was
not attempted (motions-set state explosion); the Python harness above
is the executed verification at n=3.

## T0 exit verdict

The plain-2PC stale-rule window is exhibited as required, and EFRS
eliminates the counterexample class on identical fault schedules
(EFRS column clean throughout). **T0 PASSES to ROS2 3/5/20-robot
fault-injection.** No STOP condition met.
