# RuleSync-Fleet — EFRS T0

Epoch-Fenced Rule Sync, round T0: protocol definition, formal model, and
exhaustive fault exploration for 3–5 robot fleets. No performance work,
no Gazebo, no LLM, no large implementation.

Base: single-robot RuleSync (`/Users/yulecai/Desktop/R2I-RL/rulesync` —
RuleSpec + PREPARE/(READY|REJECT|TIMEOUT) + durable WAL COMMIT +
certificate-bound application on exact (txn_id, epoch, target_hash)).

## Layout

- `docs/EFRS_T0_CONTRACT.md` — frozen protocol (snapshot, lease/fence,
  motion gate, state machines, fault model, I1..I7, exit rule).
- `docs/EFRS_T0_BASELINE_COMPARISON.md` — executed results + traces.
- `docs/EFRS_T0_THEOREM.md` — preliminary bounded theorem statement.
- `docs/EFRS_T0_NOVELTY_BOUNDARY.md` — Gate 7 audit.
- `model/fleet_checker.py` — executable exhaustive harness (run:
  `python3 model/fleet_checker.py`; deterministic; exit 0 with report).
- `model/fleet_checker_results.txt` — frozen run output.
- `model/EFRS.tla` + `model/EFRScfg*.cfg` — TLA+ gate model (TLC-clean
  on the small instance: 8,472 states, no error).

## T0 verdict

Plain-2PC stale-rule window exhibited as required; EFRS eliminates the
class on identical fault schedules (EFRS column clean: 9 systematic
schedules + 400 fuzz traces, zero I1..I7 violations). **T0 PASSES** to
ROS2 3/5/20-robot fault-injection. If EFRS had failed: STOP (not met).
