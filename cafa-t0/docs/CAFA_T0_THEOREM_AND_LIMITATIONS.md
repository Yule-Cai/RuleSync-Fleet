# CAFA-T0 Theorems and Limitations (Phase G, frozen claims)

Date: 2026-10-14. Claims frozen BEFORE experiments; each carries a
mechanical check and an adversarial program. Theorems are stated for
the frozen discrete model only — no claim transfers to arbitrary
fleets without new proof.

## T0 (foundational, must prove FIRST)

**Bounded stale-rule execution does not necessarily guarantee
immediate physical compliance after a newer rule is committed.**
Constructive proof by frozen counterexample (this IS scenario S5):
a robot physically inside the future KEEP_OUT at commit time C, under
old-rule authorization through C+L, cannot vacate instantly; any
policy that activates at C < earliest-feasible-egress violates
physical compliance while satisfying authorization bounds. Checked
mechanically: S5 under immediate activation must show a violation in
the brute-force enumerator. If S5 fails to violate, the MODEL is
broken (STOP: model cannot express the gap CAFA exists to close).

## Theorem 1 — Certificate soundness (candidate)

If CAFA returns CERTIFIED(π, T) under the stated model assumptions,
all covered trajectories satisfy the new hard-rule constraints for
all t ≥ T. Mechanical check (G2): an INDEPENDENT brute-force
trajectory enumerator (separate code path, enumerates all control
sequences × uncertainty realizations) verifies every CERTIFIED
instance across all frozen scenarios; zero false-safe required.
Adversarial program: attempt (a) stale-action freedom wider than
tubes assume, (b) partitioned-robot behavior outside the no-staging
union, (c) corridor-capacity breach inside certified plans, (d) RD
misalignment — each attempted as a concrete violating trace; any
success = Theorem 1 REFUTED → STOP.

## Theorem 2 — Bounded safe activation (candidate)

When a feasible certified transition exists within D, CAFA activates
by D or correctly reports INFEASIBLE with the failing condition.
Mechanical check: B4 oracle agreement on feasibility per instance
(feasible/infeasible verdicts must match; mismatches investigated,
not averaged away). Note the honest boundary: CAFA's INFEASIBLE is
relative to its conservative tubes — a B4-feasible/CAFA-infeasible
split measures conservatism (false-rejection metric), not a soundness
hole, PROVIDED B4 uses the same worst-case tubes (it does: shared
certificate code).

## Theorem 3 — Cost/optimality characterization (candidate)

CAFA-J is EXACT within the frozen discrete model (A* + admissible
heuristic + exhaustive T scan). Mechanical check (G4): per-instance
cost equality with B4 exhaustive DP; any gap must be explained by a
named mechanism (heuristic inadmissibility bug, pruning unsoundness,
or model mismatch) — an unexplained gap REFUTES exactness → the
claim downgrades to heuristic and G4 FAILS.

## Limitations (predeclared)

1. Discreteness: exactness holds only inside the frozen grid/speed
   model; nothing transfers to continuous dynamics.
2. Centralization: the joint planner sees shared observations; no
   distributed-protocol claim is made (EFRS provides the
   communication substrate separately).
3. Conservatism: worst-case tubes + sound pruning may reject
   feasible plans (measured; S10 bounds how often the optimum is
   "just" timed activation).
4. Partitioned robots are pure cost/risk (they can never help) —
   scenarios with permanent partitions expect INFEASIBLE or
   degraded activation, by design.
5. EMERGENCY_HOLD path is a specified failure, not a result.
