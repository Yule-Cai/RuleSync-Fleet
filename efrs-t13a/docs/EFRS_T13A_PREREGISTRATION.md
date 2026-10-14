# EFRS-T1.3a Preregistration — Healable-Workload Semantics Correction

Date: 2026-10-14. Frozen BEFORE any T1.3a implementation or experiment.
This is a NEW directory (`efrs-t13a/`); T1.2/T1.3 results, verdicts,
and JSONs are preserved untouched (FAILs stand as recorded).

## The finding (frozen, discovered post-T1.3-freeze)

`loss_random` faults NEVER honored `until` in any T1→T1.3 runner: the
branch arms permanent probabilistic drops with no scheduled disarm
(unlike partition/duplicate/loss_burst, which schedule clears). All
`until` fields written on `loss_random` faults (T1.3 `build_wheal.py`
output, T1.3 micro sched) were silently ineffectual. Consequences
already recorded: T1.2 W-HEAL (74/100) and T1.3 micro R/B both ran
under permanently stacking ambient loss, so their liveness/transport
readings are VOID (safety readings stand as sustained-loss stress).

## Scope (lead rules, binding)

- Fix the RUNNER ONLY. Forbidden to change: queue depth, QoS,
  1500 ms deadline, 100 ms retry, lease, B_real, fault durations,
  quorum, protocol state machine (coordinator/agent/fence/shim
  message logic untouched).
- `efrs_ros2/` MUST remain byte-identical to the T1.3 freeze
  (verified by hash at commit time; any diff fails the freeze).

## Runner fix (frozen design)

1. `loss_random` with `until`: schedule an automatic disarm
   (per-fault fid clear) at `until`, exactly like `loss_burst`.
   Multiple loss faults expire INDEPENDENTLY (per-fid clears; no
   cross-talk, no permanent stacking).
2. `loss_random` WITHOUT `until`: stays permanent (W-SUSTAINED
   semantics preserved byte-for-byte).
3. New shared helper `fault_harness/sched_util.py::fault_end(fault)`
   (single source of truth for fault lifetimes, used by the runner,
   the W-HEAL builder, and the GST assertion):
   loss_random → `until` if present else +∞ (permanent);
   partition/partition5 → `until`; crash_* → `restart_at` (or `t`);
   sigstop → `resume_at`; delay/duplicate/loss_burst → `until`/`t`;
   default → `t`.
4. GST + INVALID_WORKLOAD (runner-level assertions, computed at run
   start from the schedule, recorded in every record):
   - GST = max fault_end over all faults (−∞/none if no faults).
   - Fail-fast: any fault with firing time t > GST (strictly after;
     a zero-duration fault exactly at GST is degenerate but harmless)
     invalidates the schedule at startup (refuse to run).
   - Duration check: run ends (schedule cap or early truncation) before
     GST → the record is marked `"workload_valid": false` with reason
     `"no-gst-reached"` and is EXCLUDED from every liveness gate
     (INVALID_WORKLOAD, automatic, no human judgment).
   - Post-GST fault activity check: any fault FIRED with t > GST
     (should be impossible by construction) → `"workload_valid":
     false`, reason `"post-gst-fault"`.
   - Records carry `"gst"` (nullable) and `"workload_valid"` always.

## Tests (frozen, must pass pre-freeze)

- Pure (`tests/test_pure.py`): loss with until expires (fault_end ==
  until; two overlapping losses expire independently — simulated
  arm/clear ledger over the fault list); loss without until is
  permanent (fault_end = +∞); GST equals max end; empty fault list →
  GST None; W-HEAL sched file yields GST == 248.02 and all-loss-capped;
  W-SUSTAINED sched file keeps ≥1 unterminated loss (permanence
  preserved → no re-run needed).
- AST source contract: the `loss_random` branch references
  `f["until"]` and schedules a disarm; the no-until path arms without
  one; NO other fault branch changed (diff-scoped assertion).
- Behavioral (post-freeze, formal runs): W-HEAL commits resume after
  each loss expiry (observed, not asserted pre-freeze).

## Re-run plan (frozen inputs, byte-identical)

- W-HEAL: `sched-wheal.json` byte-identical to T1.3 (its `until`
  fields become effectual under the fixed runner). Sequential 1..100,
  cap 600 s. Expectation recorded here (not a gate pre-decision):
  commits resume post-expiry; 100/100 evaluated by the T1.3 G3/G4
  rules.
- Micro R/B: `sched-micro.json` byte-identical, 1x each on frozen
  T1.2-RELIABLE vs T1.3a-BEST_EFFORT stacks. Diagnostic only.
- W-SUSTAINED: NOT re-run (permanence proof above covers it).
- K13: NOT re-run (unaffected: no loss_random involved).
- M/N/Q: NOT in this round (lead: await W-HEAL 100/100 + R/B).

## Deliverables

This preregistration, fixed runner + sched_util + tests, GST-marked
records, then a T1.3a interim report. No M/N/Q. No protocol diffs.
