# Source Provenance (EFRS RA-L Draft V0)

## Inputs read completely

- efrs-p0/ (all five analysis docs + final report).
- efrs-p1/ (all four feasibility docs).
- efrs-t13a/reports/EFRS_T13A_FINAL_REPORT.md (full) and
  EFRS_T13A_REPORT.md §3 (W-HEAL accounting reconciliation).
- efrs-t13a/reports/efrs_t13a_final_results.json (keys verified).
- docs/EFRS_EVIDENCE_VALIDITY_LEDGER.md (full).
- efrs-t0/docs/ (contract, theorem, baseline comparison, novelty
  boundary — full).
- efrs-t1/docs/EFRS_T1_REPORT.md + EFRS_T1_RESEARCH_DECISION.md
  (full).
- efrs-t12/docs/EFRS_NOVELTY_BOUNDARY.md (SCOPE check).
- Implementation spot-reads for cited constants: coordinator.py
  (REACH_MS, heartbeat, COMMIT lease_ms), robot_agent.py
  (lease default), msgspec.py (topics, hash), T1 prereg (B_real).

## Discrepancies resolved before inserting numbers

- 106 PREPARE vs "attempts/update 1.0": interim report reconciles as
  ≈100 + 6 reattempt-related with ≤2 attempts per committed update;
  draft reports raw counts (≈1.06/update) and does not copy the
  rounded line (integrity item I).
- T1 witness egress ≤3.0 s vs Q ≤3.1 s: kept separate per round;
  Fig.4 uses T1 origins with T13a bounds, labeled.
- A3 7830.8 ms (T1) vs 7792.2 ms (corrected): kept separate per round.
- RSS absolute level (2 GB, unexplained-but-bounded): not in paper
  body; recorded in risk report as carried gap.

## Generation notes

- Manuscript: IEEEtran journal 10pt two-column; anonymous (no author
  block) per brief's double-anonymous instruction. RA-L's current
  review model (single- vs double-anonymous) was NOT independently
  verified — anonymity here satisfies the brief either way; lead to
  confirm house style at submission time (submission NOT authorized).
- Page count 5 (not 6): complete account fits 5 pages under the
  6-page ceiling; padding refused. No minimum exists per RAS policy.
- Figures: matplotlib vector PDF (included) + SVG + generator .py
  committed as editable sources. Fig.1 topics match msgspec.py;
  Fig.2 budgets match T1 prereg; Fig.3 values match audit rows 10–12
  + B_real; Fig.4 origins match T1 report with T13a bounds labeled.
- References: 15 entries, all verified live during P0 (Oct 15) except
  Macenski 2022 / Koenig 2004 (long-standing citations, high
  confidence) — flagged for lead spot-check before any submission.
- No text hidden in supplements; no supplement created.

## Restrictions observed

- No production code, protocol, gate, or historical-result changes
  (repo tracked-tree check before commit).
- No new experiments, schedules, or tuning.
- No SCOPE/CAFA content in manuscript (grep verified).
- No submission performed or prepared (no cover letter, no portal
  interaction).
