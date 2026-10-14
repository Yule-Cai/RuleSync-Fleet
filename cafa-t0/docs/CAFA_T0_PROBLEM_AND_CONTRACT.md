# CAFA-T0 Problem and Contract (Phase B, frozen)

Date: 2026-10-14. Frozen BEFORE candidate performance experiments.
Finite discrete model shared identically by CAFA and B0–B4.

## World

Rectangular grid W×H cells (frozen per scenario). Cell types: FREE,
WALL, CORRIDOR (capacity: at most 1 robot per corridor cell per step;
frozen capacity rule). Discrete time t = 0..Horizon (frozen H per
scenario family). A hard-rule update is a set of cells that become
FORBIDDEN (KEEP_OUT), plus optionally a SPEED_LIMIT (max speed cap
applying in marked cells; frozen per scenario, S7 only).

## Robot model (identical for all methods)

State: integer cell (x,y), heading ∈ {E,W} on lanes ({N,S} allowed in
open areas; frozen per scenario), speed v ∈ {0,1,2} cells/step.
Actions per step: {HOLD (v:=0, stay), ADVANCE (move v cells along
heading, v unchanged), BRAKE (v:=max(0,v−1), move v cells),
ACCEL (v:=min(v+1,vmax), move v cells)} subject to SPEED_LIMIT caps
and corridor capacity. Footprint: own cell + swept cells traversed.
Uncertainty: true position ∈ reported cell ± U cells (U frozen, 0 or
1); control delay: commanded action takes effect after RD steps
(RD frozen, 0 or 1); braking guarantee: from speed v, full stop
within B(v) steps under BRAKE (B(1)=1, B(2)=3 with RD=1 — frozen
table in `model/dynamics.json`).
Lease/stale model: after commit at time C, any robot may execute
OLD-authorized actions until C+L (L = stale bound in steps, frozen;
the finite analog of B_real). Partitioned robots (S4) receive NO
staging commands after partition onset: their tube assumes continued
last-authorized behavior (ADVANCE at last speed or HOLD — whichever
is worse for the certificate, i.e., union of both).
Local preparatory actions: the action set above; "evacuation" =
any path; "rerouting" = heading changes only where the scenario
graph allows (frozen per scenario; default lanes are fixed-heading).

## Rule update instance

{rule_type, current_set, new_set, commit_time C, deadline D (latest
permissible activation step), urgency weight, transition safety:
ordinary motion continues under OLD rule until activation}.
Commit/prepare/activate/reconcile exactly per brief §4 (no implicit
immediate activation). If activation at D is uncertifiable AND no
earlier T certifies: return INFEASIBLE. If the rule demands
activation NOW (D == C) while physical states forbid compliance:
return EMERGENCY_HOLD + written safety limitation (robots brake to
stop under old rule; activation deferred with logged violation of
the deadline, counted as a failure for G6).

## Certificate (Phase C, frozen rule)

Reach_i(t, H, ...) = union over ALL admissible control sequences of
swept cells from t to t+H, inflated by ±U and RD-shifted, assuming
during [C, C+L] the robot may execute any OLD-authorized action.
Activation at T certifies iff: (a) for every robot i and every
t ≥ T, Reach_i restricted to post-activation behavior avoids the new
forbidden space-time region; (b) inter-robot collisions/resource
violations are absent along the CERTIFIED preparatory plan (not
along nominal predictions); (c) partitioned robots' tubes (no-staging
union) also avoid. Nominal-trajectory checks are FORBIDDEN as
certificates. Conservative rejection is allowed but measured
(false-rejection rate metric). Certificate output: CERTIFIED(T) /
UNKNOWN / INFEASIBLE with the failing condition named.

## Costs (identical accounting, frozen weights)

downtime_i = steps with v=0 while its task is unfinished (S-family
tasks: reach goal cell; frozen per scenario); activation_latency =
T − C; interruption = steps deviated from nominal shortest path.
Objective: Σ downtime_i + W_L · latency + W_I · interruption
(W_L, W_I frozen in scenario configs). Safety violations, missed
deadlines, and infeasible declarations are NEVER tradable against
cost (G6).

## Information availability (G8)

All methods observe: reported cells (±U), speeds, headings, lease/
stale bound L, commit time C, deadline D, rule sets, corridor
occupancy of VISIBLE robots only; partitioned robots' states are
last-known + uncertainty growth. NO method sees true positions,
future faults, or other robots' private plans (joint planner sees
only the shared certified plan it outputs). The joint planner is
centralized over shared observations (declared, not a shortcut:
same input information as B3/B4).
