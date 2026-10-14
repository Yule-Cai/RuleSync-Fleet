# CAFA-T0 Eval Report (theory + finite-state novelty gate)

Status: **CONDITIONAL — STOP pending lead adjudication.** No T1 work.
No publication claims. No tuning after results (see §8 for the two
disclosed pre-report instrument corrections and the freeze-procedure
note; both predate this report, nothing post-eval was changed).

## 1. Inputs (what ran)

- Repo/host: `gamer@192.168.105.213:/home/gamer/RuleSync-Fleet/cafa-t0`,
  remote `Yule-Cai/RuleSync-Fleet`, branch `main`.
- Prereg snapshot: `5073cab` (2026-10-15 00:45 +0800).
- Eval inputs synced to host 06:11:52 (docs/model/runner), i.e. all
  design amendments below predate any eval execution.
- Killed pilot run (GO_EVAL_1, scrapped, no data published) exposed one
  B4 instrument bug (§8); clean full re-run `GO_EVAL_2.log` is THE eval.
- Results: `reports/cafa_t0_results.json` (committed with this report).
- Frozen weights: W_L=2, W_I=1, U=1, RD=1, L=2, B(1)=1, B(2)=3,
  grid 12x6, horizon 14, corridor cap 1, B_real n/a (no fleet timing).
- Tests: `tests/test_foundation.py` + `tests/test_cafa.py` pass on host
  and local (G2 frozen exhaustive set clean).

## 2. Pre-eval amendments (all 00:45→06:11, before any execution)

Post-prereg-snapshot, pre-eval, lead-directed design amendments
(committed as eval-input freeze with this report; history NOT rewritten,
delta vs `5073cab` preserved in git):

- `model/scenarios.json`: S4 resurrected with new geometry
  (R1 (1,2)→(4,2); R2 (4,5)→(8,5); R3 partitioned at (0,5);
  zone (7–11,1–3)); S1–S3/S5–S10 final geometry/flags as evaluated.
- `docs/CAFA_T0_ALGORITHM.md` (+74): CBS→prioritized-order heuristic
  downgrade disclosed with exactness boundary; CBS retained as low-level
  substrate with lineage (N9) cited as substrate-only.
- `docs/CAFA_T0_PROBLEM_AND_CONTRACT.md`: Reach corrected to
  cruise-regime continuations + as-authored plan prefix (in-flight
  commands), ±U, RD windows ("corrected pre-experiment — nothing had
  run"); TURN_L/TURN_R added (in-place to full stop).
- `docs/CAFA_T0_NOVELTY_AUDIT.md` (+18): N9 CBS lineage; claim scoped
  (joint activation plan synthesis, not search).
- `docs/CAFA_T0_THEOREM_AND_LIMITATIONS.md`: CAFA-J declared HEURISTIC;
  G4 triangulated (B4-joint + seed-agreement + local-deviation-gap).
- No scenario/doc/contract/gate text changed after 06:11 (mtimes) or
  during either eval run. No amendment followed any eval observation
  except the two B4 instrument corrections in §8 (implementation only).

## 3. Methods (as executed)

- CAFA-J: prioritized order enumeration over exact single-robot
  low-level (CBS low_level), shared CERTIFIED gate, shared cost_of,
  seeds 0/1 (agreement checked).
- B0 GlobalStop, B1 LeaseDrain, B2 IndependentGreedy, B3 TimedEfficient
  (single-robot restricted heuristic), B4 ExactJointOracle (joint
  Dijkstra + incumbent bound + NODE_GUARD 200000; scope ≤2 ACTIVE robots
  else LIMIT by disclosed design).
- G2 cross-check: independent enumerator (`model/enumerator.py`, own
  stepper) over every CERTIFIED instance; `false_safe` = capped at 8.

## 4. Results (GO_EVAL_2; wall-s in log)

| Sc | CAFA-J (T,cost,fs) | B0 | B1 | B2 | B3 | B4 |
|----|--------------------|----|----|----|----|----|
| S1 | CERT 2/8/0 | INF | INF | INF | INF | LIMIT-scope |
| S2 | INF | INF | INF | INF | INF | LIMIT-scope |
| S3 | CERT 10/23/8* | INF | INF | INF | INF | LIMIT-guard 267s |
| S4 | CERT 2/0/0 | INF | CERT 7/27/0 | CERT 2/0/0 | CERT 2/0/0 | TIE 2/0 proven 0.6s |
| S5 | CERT 9/17/0 | INF | INF | INF | INF | LIMIT-guard 130s |
| S6 | INF | INF | INF | INF | INF | INF-exhaustive 0.01s |
| S7 | CERT 2/0/8* | INF | CERT 6/10/8* | CERT 2/0/8* | CERT 2/0/8* | TIE 2/0 proven 0.7s |
| S8 | INF | INF | INF | INF | INF | LIMIT-guard 236s |
| S9 | INF | INF | INF | INF | INF | LIMIT-scope |
| S10 | CERT 2/0/0 | INF | CERT 7/30/0 | CERT 2/0/0 | CERT 2/0/0 | TIE 2/0 proven 0.8s |

`*` = enumerator lag-variant flags, capped at 8; nominal (lag-0) clean
everywhere; frozen G2 set clean. See §6 — instrument dispute, not
checker-side violations (all checker verdicts stand; zero nominal
disagreements).

Probes: T0 (S5 immediate activation violates) True. S10 tripwire
(CAFA==B3==0) True. Seed agreement True 10/10. local_opt_gap 0 wherever
a CAFA plan exists (no single-robot deviation improves). All CERTIFIED
T within [C,D]. B4 incumbent = min feasible cost (CAFA+baselines).

## 5. Ablation (G7 attribution; host /tmp probe, untracked, pre-report)

CAFA with coupling disabled (empty reservations + empty ptubes) vs B3:

| S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 | S10 |
|----|----|----|----|----|----|----|----|----|-----|
| decoupled INF (=B3 INF; coupled CERT-8) | INF | CERT-23 (B3 INF) | 0 | CERT-17 (B3 INF) | INF | 0 | INF | INF | 0 |

- S1 win is COUPLING-driven (decoupled INF → coupled CERT-8).
- S3/S5 wins are LOW-LEVEL-driven (decoupled == coupled; B3 INF).
  B3's restricted single-robot heuristic is weaker than the exact
  low-level; joint machinery unexercised there.
- 8/10 decoupled ≡ B3 (collapse holds); S3/S5 differ (exactness, not
  coupling).

## 6. Forensics: fs=8 lag-variant flags (S3, S7)

- All 10 (S3: R1/R2 × zone@10–14; S7: R1 × zone@5–9 + @10–14) are
  lag==1 ONLY (prepend-one-cruise variant); lag-0 nominal clean, all
  other scenarios/checks (stale-prefix, partitioned, inter-robot,
  corridor) clean.
- Mechanism (verified under true `dynamics.py`): the prepended cruise at
  v>0 covers ground (S7 R1 ends (6,2) vs nominal (5,2)); the shifted
  footprint touches the zone where nominal passes with 1-cell margin.
- Executor assessment: the lag-prepend (uniform whole-plan shift with
  cruise fill) is OUTSIDE the validated threat model. Contract Reach =
  cruise-regime continuations + as-authored in-flight prefix with
  RD-window ([t−RD,t]) timing jitter — i.e. timed schedules with
  skip-on-miss rejoin (stale branches), not sequence-shifted replay.
  A shifted replay desynchronizes the robot from fleet joint timing
  (the enumerator itself does not test shifted inter-robot safety —
  incoherent as a system threat). Same over-strictness class as the
  accepted T1.2 cruise-variant episode. Counter-reading: the contract
  phrase "RD-shifted" could be read as uniform shift; under that reading
  the checker (not the enumerator) has the hole → G2 FAIL.
- NO instrument change made (post-eval tuning forbidden). The flags
  stand as recorded data. RECOMMENDATION: lead adjudicates (a) accept
  over-strictness reading → approve enumerator lag-variant removal +
  re-verify, or (b) accept hole reading → G2 FAIL → STOP.

## 7. Gate adjudication (letter vs substance; lead decides all CONDITIONAL)

- G1 novelty: CARRY-PASS (pre-reg audit; T0 surfaced no new prior art;
  claim scope per amended audit).
- G2 soundness: FROZEN-SET PASS (tests green); eval-extension
  CONDITIONAL (§6). → LEAD: §6(a) or §6(b).
- G3 strict advantage (families A:{S2,S9}, B:{S4,S8}):
  LETTER-FAIL — family A all-INFEASIBLE; family B S4-tie-with-B2/B3,
  S8 all-INFEASIBLE. No CAFA strict advantage on designated families.
  SUBSTANCE: CAFA-only-feasible strict wins on S1/S3/S5 (off-family).
  → LEAD: amend families/wording (e.g. count S1/S3/S5) or STOP.
- G4 B4-equality: PROVEN on S4/S7/S10 (TIE cost 0, proven optimal) +
  S6 exhaustive INFEASIBLE-agreement; INCONCLUSIVE on S3/S5/S8
  (200k-node guard; S8 no method feasible); OUT-OF-SCOPE on S1/S2/S9
  (3-active > B4 scope, disclosed design). local_gap 0 + seed 10/10
  support where B4 is silent. → LEAD: sufficiency for a T0 gate.
- G5 greedy insufficiency (witnesses S2/S8/S9): LETTER-VACUOUS
  (B2 fails on all three ✓ literally) / SUBSTANCE-FAIL (CAFA fails
  there too; S8/S9 design intent — feasible-but-greedy-fails — not
  realized). Real greedy-insufficiency at S1/S3/S5 (off-witness).
  → LEAD: amend witness set or STOP.
- G6 no-benefit-from-violations: PASS (zero checker-side violations;
  zero deadline misses; INF reported as INF; §6 flags are
  enumerator-side and untraded).
- G7 irreducibility: tripwire PASS (S10 CAFA≡B3=0, True); ablation MIXED
  (§5: S1 coupling-attributed ✓ purpose served; S3/S5 low-level wins;
  joint machinery otherwise unexercised). → LEAD: sufficiency; T1 needs
  coupling-forcing scenarios either way.
- G8 information parity: PASS by code inspection (this report).
  All methods consume reported cells (±U), speeds, headings, lease/
  stale bound L, C/D, rule sets, visible corridor occupancy;
  partitioned robots as last-known + growth only. No method sees true
  positions, future faults, or others' private plans. The joint planner
  (CAFA-J, B4) is centralized over the shared certified plan it outputs
  — declared in contract §Information-availability, same input
  information as B3. No privileged channels found in
  `algorithms/cafa.py`, `algorithms/cbs.py`, `baselines/*`,
  `model/enumerator.py`, `run_eval.py`.

OVERALL: T0 does not unilaterally pass. STOP. Decisions required:
(1) §6(a)/§6(b); (2) G3 amend-or-stop; (3) G4 sufficiency;
(4) G5 amend-or-stop; (5) G7 sufficiency.

## 8. Disclosed pre-report instrument corrections (B4 only)

Two genuine implementation bugs fixed between the scrapped pilot and the
clean re-run (killed-run data discarded; full clean re-run after; frozen
scenarios/dynamics/contract/gates untouched):

1. B4 expanded PARTITIONED robots as moving agents AND checked their
   footprints against their own frozen tubes → self-prune → INFEASIBLE
   on feasible S4 (pops=11, pushes=0; sole outlier vs cafa.py/B0–B3
   which all freeze partitioned). Fix: expand ACTIVE robots only;
   partitioned get `[]` (mirrors `cafa.py`). Before: S4 INFEASIBLE;
   after: proceeds (then TIE-0 with fix 2).
2. B4 authored joint-length plans (trailing goal-holding HOLDs counted
   by cost_of as interruption: proven-"optimal" cost 1 vs CAFA 0 for the
   same physics). Fix `_truncate_holds`: drop trailing HOLDs whose
   pre-state is at goal — physics-identical (dropped HOLD ≡ checker's
   HOLD-pad; check re-verifies) — matching the arrival-length
   representation CBS-low_level/B0–B3 author. Before: S4 TIE-1;
   after: S4 TIE-0 proven.
3. Both fixes make B4 a fairer (stronger-or-equal) oracle; neither
   touches scores except via B4's own correctness. Local + host tests
   re-pass after the fixes.

## 9. Artifacts & reproduction

- `reports/cafa_t0_results.json` (frozen eval record),
  `GO_EVAL_2.log` (kept on host execution dir; not committed),
  `run_eval.py`, `model/*`, `algorithms/*`, `baselines/*`, `tests/*`.
- Reproduce: host `python3 run_eval.py` (seeds fixed; ~25 min).
  B4 guard LIMITs are expected (S3/S5/S8) and scope LIMITs by design
  (S1/S2/S9).
