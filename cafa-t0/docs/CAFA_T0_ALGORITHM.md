# CAFA-T0 Algorithm (Phase D, frozen)

Date: 2026-10-14. Candidate: **CAFA-Joint (CAFA-J)**: centralized
finite-horizon joint search over (preparatory joint actions × shared
activation time) with worst-case tube certificates. Frozen before any
performance experiment; code must implement exactly this.

## 1. Optimization problem

minimize  Σ_i downtime_i(π, T) + W_L·(T − C) + W_I·interrupt(π)
over joint preparatory plan π = (a_1..a_N)_{t=C..T−1} and activation
step T ∈ [C, D], subject to:
(a) CERTIFIED(T) under §5 tubes (worst-case, incl. partitioned robots
    with no-staging union and [C, C+L] old-action freedom);
(b) corridor capacity ≤ 1 per cell per step along π;
(c) SPEED_LIMIT caps (S7) along π and after T;
(d) EFRS semantics: no robot executes new-rule-constrained motion
    before T; partitioned robots receive no commands after partition.
If no (π, T) certifies with T ≤ D: return INFEASIBLE (never an
uncertified T).

## 2. State / transitions

Search state: (time t, joint physical states incl. speeds/headings,
staged reservations, activated flag). Initial: scenario start at C
(commit known). The joint planner is PRIORITIZED PLANNING OVER
ORDERINGS (amended pre-experiment — nothing had run: joint Dijkstra
explores cost plateaus × RD pipeline variants intractably, and CBS
cell-time branching does not terminate under windowed-footprint
conflicts. Prioritized enumeration is tractable and its exactness
boundary is stated honestly in §7): for each permutation of robots,
sequential tube-compliant low-level optima (exact single-robot
Dijkstra under space-time reservations) avoiding earlier robots'
full windowed traces; joint CERTIFIED gate on every assembled plan;
min cost wins. Outer scan over T unchanged (exhaustive).

## 3. Pseudocode

  CAFA-J(scenario):
    for T in C..D:                                   # candidate times
      if not quick_reject(T):                        # per-robot tube precheck
        π, cost = joint_search(C, T)                 # A* over joint actions
        if π is None: continue                       # infeasible for this T
        if CERTIFIED(π, T): return (π, T, cost)       # full joint certificate
    return INFEASIBLE                                 #_try in T order: earliest
    # certified T first → minimal latency bias; cost comparison below.
    joint_search: PRIORITIZED PLANNING over all N! robot orderings
      (amended pre-experiment — nothing had run; joint exact search
      is intractable in this state space (cost plateaus × RD pipeline
      variants; measured multi-minute per (scenario, T) with no
      completion), and CBS cell-time branching does not terminate
      under windowed-footprint conflicts (demonstrated 2700-node
      ping-pong on S1). Per (order, T): sequential exact single-robot
      optima (Dijkstra) under space-time reservations from earlier
      robots' full windowed traces + own tube compliance; shared
      CERTIFIED gate on every assembled plan; min cost wins. B4
      (independent joint-Dijkstra engine, 2-active-robot scope) stays
      the exact reference where computable (G4).
    CERTIFIED(π, T): exact tube check per §5 (enumerated control
      sequences up to H past T + braking tails to stop).

## 4. Feasibility test

quick_reject(T): per-robot independent tube check (as in B2's
per-robot planner); if ANY robot's tube unavoidably enters the
forbidden set by T under all its options → T infeasible without
joint search. INFEASIBLE overall only after all T ∈ [C, D] rejected.

## 5. Complexity

Branching ≤ 4^N joint actions (pruned), depth ≤ D − C + task tail.
Worst case exponential in N and horizon (expected; instances are
tiny by design). A* with admissible h is optimal within the
discretized model (see §7). Runtime measured (metric).

## 6. Soundness theorem candidate

If CAFA-J returns (π, T) CERTIFIED, then every physically possible
robot trajectory consistent with the uncertainty model satisfies the
new hard-rule constraints for all t ≥ T (proof obligation: tube
construction covers old-action freedom [C, C+L], RD shift, ±U,
braking tails, partitioned no-staging union; MECHANICAL CHECK below
tests certificate against an independent brute-force trajectory
enumerator on all frozen instances — zero false-safe = G2).

## 7. Optimality / approximation

CAFA-J is a HEURISTIC (prioritized order enumeration). Joint optima
requiring true simultaneity beyond orderings can be missed; the gap
is measured against B4 where computable (G4), and B4 LIMITs bound
the scope of that measurement. This is a deliberate, disclosed
downgrade from "exact joint algorithm" (intractable here): the
paper-level contribution, if gates pass, is certified joint
activation PLANNING with measured wins — never an optimality claim
beyond what G4 evidences. No approximation is hidden inside:
low-level optima are exact under reservations; order coverage is
total (all N! permutations); incompleteness comes only from
interleaved sharing outside orderings. COMPLETION_CAP / heap-cap
LIMITs report LIMIT (never a truncated certificate) — a LIMIT on
any gate-relevant instance is disclosed as scope loss, not success.
Known exactness boundary (predeclared): memoization is on full
(t, joint-state) including RD pipeline state, so no
prefix-dominance shortcut is taken anywhere — at the cost of speed.

## 8. Failure / infeasibility conditions (explicit)

INFEASIBLE: no certified T ≤ D (S6 by design; S5 possible).
EMERGENCY_HOLD: D == C with noncompliant states (logged deadline
violation = G6 failure if it ever fires outside S6-design).
False rejection: certified-feasible plan rejected by conservative
tubes/pruning — measured, not hidden (metric; threatens G3 claims
if large).

## 9. Novelty limitation (self-declared, binds G7)

CAFA-J combines: timed activation (N2) + worst-case reachability
filtering (N6/gatekeeper) + prioritized multi-robot planning (a
standard coordination pattern in the CBS/MAPF lineage — N9 is cited
as prior art for the search family, never claimed). If evaluation
shows its decisions coincide with B3+braking-check on all coupled
families (S10 generalized), the contribution reduces to "timed
updates plus standard filtering" and the verdict MUST be
NOVELTY_WEAK regardless of cost wins from tuning. The claimed
substance, if any survives G3/G5/G7, is the ADAPTATION
(tube-certified activation-time co-optimization under lease/partition
semantics with joint downtime/latency objective) — never the search,
the filter, or the update abstraction alone. G5 (IndependentGreedy
insufficiency counterexample) + G3 (strict advantage on TWO coupled
families) are the load-bearing gates.
