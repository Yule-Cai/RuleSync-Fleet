# EFRS Evidence Validity Ledger

Date: 2026-10-14. Research-lead ordered. This file changes NO
historical raw JSON or report values; it only labels their VALIDITY
for stated purposes. All paths relative to repo root.

## INVALID_FOR_EVENTUAL_HEAL_LIVENESS
## (usable only for sustained-loss / congestion / safety diagnostics)

Reason (frozen finding): `loss_random.until` never fired in any
T1→T1.3 runner, so ambient loss stacked permanently instead of
healing. These runs never tested eventual-heal liveness.

- `efrs-t12/experiments/t12_scale/rec-wheal.json`
  (74/100; the T1.2 W-HEAL formal run)
- `efrs-t11/experiments/t11_scale/rec-scale20-replay.json`
  (12/100; the T1.1 exact-trace replay)
- `efrs-t1/experiments/t1_20robot/rec-scale20.json`
  (0/100; the original T1 scale counterexample — ALSO valid,
  unchanged, as the frozen T1 negative result and as sustained-loss
  safety stress)
- Safety readings inside the above (stale bounds, fence HOLD counts,
  local ledgers where present) REMAIN VALID as sustained-loss /
  congestion / safety diagnostics. Liveness/commit-count readings
  from them are VOID.

## NOT_VALID_FOR_TRANSPORT_CAUSAL_INFERENCE

- `efrs-t12/experiments/t13micro/rec-microR.json` (R, RELIABLE) vs
  `efrs-t13/experiments/t13a_micro/rec-microB2.json` (B, BEST_EFFORT):
  workload semantics differ by runner generation (R permanent loss
  vs B healing loss). The pair is diagnostic only; it does NOT
  isolate transport. No BEST_EFFORT-superiority claim may rest on it.

## VALID_EVENTUAL_HEAL_EVIDENCE

- `efrs-t13a/experiments/t13a_scale/rec-wheal.json`
  (100/100, workload_valid gst-reached, GST=248.02): the accepted
  valid eventual-heal execution. Fixed runner `e00bb05d`.
- Supporting: `efrs-t13a/experiments/t13a_micro/rec-microB2.json`
  (8/8 through a 3 s loss, gst-reached) and
  `efrs-t13a/experiments/smoke/rec-disarm.json`
  (abort-then-commit across loss expiry, GST=7.0 gst-reached).

## TRANSPORT HYPOTHESIS STATUS

RELIABLE-many-to-one ACKNACK/repair implosion: SECONDARY OPEN
HYPOTHESIS — NOT ESTABLISHED. Primary explanation of previous
W-HEAL failures: WORKLOAD_SEMANTICS BUG (above). No further
transport comparison is authorized on current evidence.
