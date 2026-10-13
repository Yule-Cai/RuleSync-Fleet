# EFRS-T1 Final Report (ROS2 fleet fault-injection gate)

Date: 2026-10-12. Implementation agent record; verdicts per research-lead
decisions. B_real = 1300 ms (1000 lease + 50 guard + 250 jitter), frozen.

## Verdict (lead-blessed)

- **SAFETY: PASS.** Every executed safety gate passes with zero
  contradictory evidence: 3-robot deterministic matrix (16/16 EFRS
  cells), 30x campaign (1440 runs), 5-robot systematic + combos (11
  schedules), I2/I2B, physical Gazebo witness (3x EFRS + 3x 2PC).
  Stale execution everywhere bounded (max 181.3 ms vs 1300 ms bound).
- **LIVENESS (20-robot scale): FAIL.** 0/100 epochs committed; the
  coordinator wedged permanently after the first vote round (13/20
  READY within the single-shot 1500 ms window, no retransmit / abort /
  retry path), swallowing the remaining 99 proposes silently.
- **T1 OVERALL: FAIL → STOP.** 100 proposals are not 100 committed
  epoch updates; the frozen scale objective is not satisfied. A halted
  fleet exhibiting zero stale motion is correct fail-safe behavior, not
  protocol success. No re-run, no window/parameter/quorum change, no
  retry patch (frozen-code discipline). The scale-20 0-commit trace
  stands as formal counterexample / negative evidence below.
- Next: awaits research lead on whether to open an EFRS-T1.1
  liveness-repair preregistration.

## Provenance (dual-freeze chain)

- T1 freeze: commit `fa9310e`; `fault_harness/runner.py` sha256
  `59aeb6a42281`. Stamps ALL deterministic evidence (matrix,
  ablations, I2/I2B, 5-robot, 30x, scale-20).
- Witness-only amendment: commit `3c08041`; runner sha256
  `5e2e82011ebd72c07ee1117f1f2244e91e616d0c449991a9605e491f4e7e87b2`
  (`--motion-source external` + pre-run sweep; `efrs_ros2/` untouched).
  Stamps witness records only. Full chain in
  `docs/EFRS_T1_PREREG_ADDENDUM_WITNESS.md`.
- Gate quantities via `fault_harness/analyze.py`: `contradictory` =
  epoch_mismatch + invalid_lease + unreconciled (must be 0);
  `fleet_stale_max_ms` vs B_real; `authorization_expired_accepts`
  counts race-bounded in-flight executions (reported, bounded by stale).
  Official aggregations: `aggregate.py` (matrix), `rep_aggregate.py`
  (30x: `efrs_faults_over_gate: []`, 48/48 cells).

## 3-robot deterministic matrix (EFRS; frozen stamp 59aeb6a4)

stale_max ms / auth_expired(race) — contradictory 0, rollbacks 0, all
16 cells: F0 145.3/0, F1 0.0/0, F2 145.6/0, F3 0.0/3, F4 153.8/0,
F5 54.5/0, F6 0.0/0, F7 0.0/0, F8 24.5/0, F9 0.0/0, F10 21.5/2,
F11 92.4/2, F12 0.0/0, F13 0.0/0, F14 95.9/1, F15 103.1/0.
Baselines reproduce stale-window counterexamples on the same faults
(broadcast F3/F6/F7/F11/F13/F15: 7.7–12.5 s stale; 2PC F6/F7/F11/F13:
7.9–12.7 s; 2PC F12: 90 rollbacks).

## 30x campaign (1440 runs, n=30/cell, frozen stamp)

EFRS per-fault max/mean stale ms (contradictory 0, rollbacks 0, all
cells): F0 178.0/129.2, F1 0.0/0.0, F2 168.0/129.7, F3 0.0/0.0,
F4 181.3/115.3, F5 160.3/89.1, F6 176.8/102.5, F7 178.2/117.1,
F8 127.3/31.8, F9 94.6/31.4, F10 177.5/46.7, F11 176.1/125.0,
F12 0.0/0.0, F13 94.2/24.9, F14 176.6/131.7, F15 179.9/122.9.
Overall EFRS max 181.3 ms (7x under B_real). Race-bounded auth accepts
(F3/F7/F8/F9/F10/F11/F14 sums 3–214/30 reps) reported, all within the
stale bound. Baseline cells show multi-second stale means (e.g. 2PC F6
mean 10466.5 ms) — the effect EFRS removes.

## 5-robot + I2/I2B (frozen stamp; stale ms / contradictory)

P41 163.1/0, P32 128.4/0, P2ISO 119.6/0, PCOORD 0.0/0,
C_PLUS_LATE 0.0/0, C_PART_RESTART 133.8/0, C_COORD_ROBOT 134.7/0,
C_LOSS_REORDER 0.0/0, C_STALE_RECONNECT 141.1/0, I2 50.3/0,
I2B 115.1/0. All ≤163.1 ms, zero contradictory, zero rollbacks.

## Ablations (positive controls, frozen stamp)

A1 (fence removed): 31 auth accepts. A2 (lease removed): 32 auth
accepts. A3 (T0 renewal path restored): 7830.8 ms stale — reproduces
the T0 renewal bug. Each ablation breaks exactly the mechanism it
removes, confirming the safety result is load-bearing on the fence.

## Physical Gazebo witness (amended stamp 5e2e82; 3x EFRS + 3x 2PC)

Scenario (45 s): R3 partitioned t=2→25 s; epoch 1 (north KEEP_OUT
x∈[4,8], y∈[0,2]) proposed t=5 s. Epoch-gated metric: in-zone samples
while locally committed to epoch ≥1 (pre-commit transit allowed;
egress after commit must be prompt).
- EFRS (wit-efrs11/12/13, identical): R3 lease-HELD 112x across the
  partition (fence `lease-expired`), healed, reconciled (epoch 1
  observed), egressed south ≤3.0 s, detoured (y→−1.5), resumed to goal.
  Runner stale_max 0.0–106.5 ms. Connected robots egress ≤3.0 s.
- 2PC (wit-2pc6/7/8, identical): R3 never committed (epoch 1 never
  observed), 228 fence verdicts `no-gate`, drove the stale nominal
  route straight through the zone (95 in-zone samples), never detoured;
  runner stale_max 40.4–40.5 s.
- Bring-up defects corrected and disclosed: bridge/GZ-partition
  mismatch (zero odometry), absolute-topic `__ns` non-remap (explicit
  `-r` remaps added), epoch-ungated counting (violations now carry the
  observed epoch + `epoch1_observed_at`), no-stop route end (fenced
  zero-velocity), mid-route re-plan with southern egress on epoch
  switch. All symmetric across protocols; R3 contrast replicated 3x.

## Scale-20 counterexample (formal negative evidence, frozen stamp)

`experiments/t1_20robot/rec-scale20.json` (265 s, 20 agents + 20
fences, 100 proposes t=1.5–249 s, 20% loss from t=5 s, partition
groups ≤3 robots ≤20%): **0 commits**, WAL empty, 1053 fence events
(816 gate-pass epoch-0, 237 correct `lease-expired` HELDs), 7276 agent
states all epoch 0, 0 stale motions.
Root cause (evidence-backed): coordinator `decide()` commits iff EVERY
reachable robot voted READY (T0 unanimity rule) inside a single-shot
1500 ms vote window; on timeout with incomplete votes it returns
silently — no prepare retransmit, no abort, no retry. Only 13/20 READY
arrived in round 1 (41-node discovery storm + loss); `prepared` stayed
set, so all 99 subsequent proposes were rejected silently
(`propose()` early-return, no log). 0 ABORT/COMMIT lines; 2767 INFO
lines end in teardown RCLError.
Disposition: fail-safe behavior correct (fences held every stale
command for 265 s; CPU ~30%), but liveness objective not met. No
tuning performed. This trace is the T1.1 starting point, not a
debugging backlog: any liveness repair (retransmit/abort-retry/window)
changes frozen coordinator semantics and requires a new preregistration.

## Deviations / amendments

1. In-node deterministic shim for ALL impairments instead of netns/tc
   (frozen in prereg §Honest mechanism deviation; byte-replayable JSON
   schedules; ROS/DDS/crash/clocks real).
2. Dual-freeze chain for the witness (addendum 3c08041; §Provenance).
3. Witness bring-up fixes (§Physical witness) — harness configuration,
   symmetric, outcome-independent.
4. Sealed-test discipline, no-overwrite evidence, sequential execution —
   held throughout. 30x reps, matrix, scale stamp the frozen runner;
   witness stamps the amended runner; no record overwritten.
