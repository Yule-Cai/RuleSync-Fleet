# CAFA-T0 Preregistration (metrics, gates, frozen configuration)

Date: 2026-10-14. Frozen BEFORE candidate performance experiments.
Scenarios: `model/scenarios.json` (S1–S10, dynamics, weights, horizon;
no seeds needed — fully deterministic finite instances; B4 search
limits: full exhaustive, no node cap except a 200k-state guard that
reports LIMIT instead of a certificate).

## Metrics (§10, identical accounting for CAFA, B0–B4)

safety_violations, false_safe_certificates (vs brute-force enumerator),
certified_feasibility (CERTIFIED/UNKNOWN/INFEASIBLE/EMERGENCY_HOLD per
instance), activation_latency (T−C), total_downtime, per-robot
interruption, false_rejection_rate, optimizer_runtime_s,
optimality_gap_vs_B4, cost_vs_B0–B3, failure/infeasibility counts.
Infeasible scenarios (S6-design, S5-possible) stay in ALL summary
statistics (correct-reporting scored separately from cost). Pareto:
downtime vs activation delay per scenario family. Cost comparisons
are valid ONLY at equal safety (zero violations both sides).

## Gates (§11, ALL must hold or STOP, no tuning after results)

G1 novelty (audit + below). G2 soundness: zero false-safe on the
frozen exhaustive set (independent enumerator). G3: strict advantage
— on BOTH coupled families (A: S2+S9; B: S4+S8) CAFA non-dominated
and strictly better than EVERY non-oracle baseline at common feasible
safety. G4: per-instance cost equality with B4 or justified bounded
gap. G5: IndependentGreedy insufficiency counterexample (at least one
of S2/S8/S9 where greedy fails or pays strictly more). G6: no benefit
from violations/concealed infeasibility/post-deadline activation
(enforced: violations/deadline-misses dominate any cost win).
G7: irreducibility (S10 tripwire: CAFA ≡ B3 on S10 within accounting;
plus G3/G5 wins must come from coupling, shown by ablation: CAFA
with coupling disabled must collapse to B3-like results).
G8: information parity (single audit of observation use in code).

## Frozen configuration record

dynamics.json (B-table, U=1, RD=1, L=2, capacity 1), scenarios.json,
weights (W_L=2, W_I=1), horizon 14, B4 guard 200k states. Any
post-result change to geometry/weights/constraints/components =
gate failure by definition.
