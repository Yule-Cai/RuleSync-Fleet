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
(commit known). Transitions: joint actions (product of per-robot
{HOLD, ADVANCE, BRAKE, ACCEL} pruned by caps/capacity) + a special
ACTIVATE(t) transition enabled only if the certificate check passes
for T = t. Goal: all tasks finished AND activated with T ≤ D.
Costs accumulate per contract weights.

## 3. Pseudocode

  CAFA-J(scenario):
    for T in C..D:                                   # candidate times
      if not quick_reject(T):                        # per-robot tube precheck
        π, cost = joint_search(C, T)                 # A* over joint actions
        if π is None: continue                       # infeasible for this T
        if CERTIFIED(π, T): return (π, T, cost)       # full joint certificate
    return INFEASIBLE                                 #_try in T order: earliest
    # certified T first → minimal latency bias; cost comparison below.
    joint_search: A* with admissible heuristic h = Σ remaining shortest
      path steps (ignoring coupling) + 0 latency term; expands joint
      actions; prunes corridor conflicts, cap violations, and states
      whose per-robot tube already intersects the future forbidden set
      (sound pruning: only provably hopeless branches cut).
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

Within the frozen discrete model, A* + admissible h + exhaustive T
scan returns the optimal (π, T) pair: EXACT (no gap) — B4 cross-check
(G4) must confirm equality on all instances, else report the gap
mechanism honestly. No approximation is built in; if search limits
are hit (frozen node cap), the run reports INFEASIBLE (never a
truncated "best-effort" certificate) — node-cap hits counted.

## 8. Failure / infeasibility conditions (explicit)

INFEASIBLE: no certified T ≤ D (S6 by design; S5 possible).
EMERGENCY_HOLD: D == C with noncompliant states (logged deadline
violation = G6 failure if it ever fires outside S6-design).
False rejection: certified-feasible plan rejected by conservative
tubes/pruning — measured, not hidden (metric; threatens G3 claims
if large).

## 9. Novelty limitation (self-declared, binds G7)

CAFA-J combines: timed activation (N2) + worst-case reachability
filtering (N6/gatekeeper) + centralized joint search (standard A*.
If evaluation shows its decisions coincide with B3+braking-check on
all coupled families (S10 generalized), the contribution reduces to
"timed updates plus standard filtering" and the verdict MUST be
NOVELTY_WEAK regardless of cost wins from tuning. G5 (Independent-
Greedy insufficiency counterexample) + G3 (strict advantage on TWO
coupled families) are the load-bearing gates.
