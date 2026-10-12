# EFRS-T1 Preregistration Addendum — Physical (Gazebo) Witness Harness Amendment

Date: 2026-10-12. This addendum extends `EFRS_T1_PREREGISTRATION.md`
without altering any preregistered protocol semantics, bounds, faults,
or success criteria. It records a second, witness-scoped freeze in the
test harness, forced by a harness-isolation defect discovered during
Phase-K witness bring-up.

## Dual-freeze chain

- Original T1 freeze (protocol + harness): commit `fa9310e`;
  `efrs-t1/fault_harness/runner.py` sha256 `59aeb6a42281`.
  All deterministic evidence (48-schedule matrix, ablations A1/A2/A3,
  I2, I2B, 5-robot systematic + combos, 30x campaign = 1440 reps) is
  stamped `59aeb6a42281` and KEEPS that freeze identity. It is not
  re-run and not re-labeled.
- Amended witness-only freeze: `efrs-t1/fault_harness/runner.py`
  sha256 `5e2e82011ebd72c07ee1117f1f2244e91e616d0c449991a9605e491f4e7e87b2`,
  plus `efrs-t1/fault_harness/run_one.sh` pre-run sweep.
  Effective freeze for the physical Gazebo witness ONLY.

## Exact changes (harness isolation only)

1. `runner.py`: `--motion-source {runner,external}` flag (default
   `runner`). With `external`, the runner skips its internal
   `motion_tick()` and only drives faults / proposes / metrics; motion
   commands come exclusively from the external waypoint drivers via
   `/efrs/motion_cmd`. The schedule file carries
   `"motion_source": "external"`.
2. `run_one.sh`: pre-run sweep killing leftover stack processes and
   `d1-lyrical` containers so each run starts clean. Operational
   hygiene; no protocol or scheduling semantics.

## Reason

The frozen runner's `motion_tick()` unconditionally publishes
`vx=0.1 m/s` drift commands to `/efrs/motion_cmd` every 0.2 s — the
SAME topic the witness waypoint drivers use. Under a physical witness
(`motion_plan: external`), these harness-originated commands are
indistinguishable from driver commands at the MotionFence, i.e.
harness-induced motion contamination. The amendment removes the test
harness's own interference; it does not change EFRS behavior.

## Explicitly unchanged

- `efrs_ros2/` protocol code (coordinator, robot_agent, motion_fence,
  shim, wal, msgspec): byte-identical to `fa9310e`.
- Coordinator / agent / MotionFence semantics; lease duration 1000 ms;
  heartbeat 100 ms; guard 50 ms; jitter 250 ms; B_real = 1300 ms.
- Invariants I1–I7; fault schedule (witness: R3 partition t=2→25 s,
  epoch-1 propose t=5 s); baseline definitions (2PC = `--no-lease-expiry`
  + `--ignore-lease`, per `runner.py:91-92`).
- Witness success/failure criteria (per
  `docs/EFRS_T1_GAZEBO_WITNESS_DESIGN.md`).

## Chronology (anti-HARKing)

- The amendment entered the runner BEFORE any amended-runner witness
  record was collected (witness series wit-efrs10+ / wit-2pc6+).
- The amendment decision was driven by the contamination finding
  (odom-link debugging 2026-10-12), not by any witness outcome; no
  witness result was known when the flag was introduced.
- Re-running the witness on the frozen runner was rejected because it
  would deliberately reintroduce known motion contamination.
- Quarantine of the witness was rejected absent any evidence that the
  amendment alters protocol/fault semantics rather than harness
  isolation.

## Witness evidence covered by this addendum

- `experiments/t1_gazebo/wit-efrs{10,11,12,13}/` + `wit-2pc{6,7,8}/`
  (records, vio tracks, fence-verdict events), superseding the
  contaminated bring-up series (empty odometry: GZ-partition and
  absolute-topic remap defects, documented in the final report).
- Witness harness scripts (`witness_launch.sh`, `witness_run.sh`,
  `waypoint_driver.py`, `twist_translator.py`, `sched-witness-*.json`,
  per-robot SDFs) are experiment configuration, not frozen protocol.
