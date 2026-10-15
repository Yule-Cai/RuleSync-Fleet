# CAFA-T0 Final Research Decision (research-lead ruling)

Date: 2026-10-15. Authority: research lead. Executor record only.

## Verdict

**CAFA-T0 = FAILED. NO CAFA-T1 AUTHORIZED.**

## Gate record (final, supersedes any looser wording in the T0 report)

- G1: preliminary novelty boundary only. The audit delimits prior art;
  no novelty claim is established.
- G2: UNRESOLVED; soundness not fully established. The lag-1
  enumerator counterexamples (S3, S7) are retained as open
  counterexamples. No instrument change was or will be made to obtain
  a pass.
- G3: FAIL. Designated families unamended (A:{S2,S9}, B:{S4,S8}).
- G4: INCONCLUSIVE. No B4 outcome — guard-limited, scope-limited, or
  otherwise — is classified as an optimality proof. The T0 report's
  "proven optimal" phrasing for B4 TIE rows is hereby superseded.
- G5: FAIL. Failed witnesses not replaced (S2/S8/S9 stand as run).
- G6: PASS subject to G2 scope (no checker-side violations traded;
  soundness scope itself remains per G2-unresolved).
- G7: algorithmic contribution not established (tripwire passed, but
  attribution does not support a joint-coupling contribution claim;
  S3/S5 wins are low-level-driven and S1 is exploratory, see below).
- G8: PASS (information-parity audit as recorded in the T0 report).

## Standing of positive observations

S1/S3/S5 CAFA-only-feasible outcomes remain EXPLORATORY. They support
no publication claim, no optimality claim, and no novelty claim.

## Disclosure (carried, complete)

- Preregistration/evaluation input changes (post-`5073cab`-snapshot,
  pre-eval design amendments: S4 geometry, heuristic downgrade, Reach
  correction, TURN actions, G4 triangulation) are fully disclosed in
  `reports/CAFA_T0_REPORT.md` §2 and frozen by commit `fa152c5`.
- B4 instrument corrections (active-only expansion, arrival-length
  truncation) are fully disclosed in `reports/CAFA_T0_REPORT.md` §8.
  They are recorded as executed fact, not as validated improvements,
  and no B4-based optimality conclusion is drawn from them.
- Raw artifacts preserved: `reports/cafa_t0_results.json`, host
  `GO_EVAL_2.log`, all implementation, tests, and probes. Nothing
  deleted, nothing rewritten.

## Constraints observed in this closeout

- Designated G3 scenario families NOT amended.
- Failed G5 witnesses NOT replaced.
- No incomplete B4 search classified as an optimality proof.
- Lag-1 safety counterexamples NOT removed.
- Protocol, scenarios, benchmarks, gates: UNMODIFIED.
- No new experiments executed.

## Closeout

Negative closeout committed and pushed. Work stops here.
No CAFA-T1. No further analysis runs.
