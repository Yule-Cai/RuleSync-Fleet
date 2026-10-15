# EFRS-P0 Paper Claim Matrix (existing evidence → claim; gaps; SCOPE check)

Rule: frozen results only; no new statistics; runs are not
independent confirmations of each other (same code/harness lineage).

## 1. Claim → evidence mapping

| Claim | Supporting frozen evidence | Scope/limit |
|---|---|---|
| Plain-2PC/broadcast admit stale-rule windows | T0 S1/S6/S8 counterexamples; T1 baselines multi-second stale (7.7–12.7 s); 2PC F12 90 rollbacks; 2PC Gazebo 40.4 s straight-through | Holds; baselines are the T0/T1 frozen controls |
| EFRS eliminates the exhibited counterexample class on identical schedules | T0 9-sched + 400 fuzz clean; T1.2 G1 host rerun (17/17 + 200-seed fuzz clean) | Bounded instances (n≤5, horizons stated); NOT unbounded proof |
| Stale execution bounded by B_real=1300 ms | Matrix max 153.8 ms; 30x max 181.3 ms; 5-robot ≤163.1 ms; W-HEAL 263.2 ms; M cell-max ≤552 ms; N ≤184 ms; Q 58–130 ms; ledgers gate_ok throughout | Empirical margins only; budgets (§G A2/A3) unstressed near bound |
| Fence is load-bearing (not decorative) | A1 (31 accepts), A2 (32 accepts), A3 T0-bug reproduction 7830.8 ms + T1.3a-corrected 7792.2 ms; ledger-join audits | Positive controls; A3 original broken run retained |
| Lease-HOLD fail-safe under degradation | T1 scale-20: 237 lease-HOLDs, zero stale motion over 265 s | Correct fail-safe ≠ protocol success (frozen verdict) |
| Eventual-heal liveness repair works | T1.3a W-HEAL 100/100 (GST=248.02, heal-to-commit ≤2.06 s); M 480/480 gate_ok; N 8/11 + amended restart [1,2]; microB2 8/8 | Workload-heal only; permanent-loss tails INCONCLUSIVE (T1.1); congestion hypothesis downgraded; ACK uncounted; RSS level unexplained-but-bounded |
| Coordinator restart safe | N C_COORD_ROBOT amended [1,2]: epoch recovered, ONE replay, ep2 +0.18 s, rollbacks 0 | Single amended run + diagnostics; ORDER DEVIATION disclosed, stands or falls on lead adjudication |
| Integrity enforcement (I2) | I2/I2B: 341/230 fence rejections, legit epochs unaffected, stale ≤115 ms | In-flight mutation only; Byzantine coordinator outside model |
| Physical behavior | Q 3/3: partition → 112–113 lease-HELDs → heal → reconcile → egress ≤3.1 s → detour → resume; T1 witness 3x same shape | Egress latency observed, not bounded; residuals irreducible |
| Liveness limits (negative) | T1 0/100 (frozen counterexample); T1.1 12/100; T1.2 74/100 void-run | Retained as negative evidence; repair path disclaimed generic |

## 2. Claims with NO support (must not appear in any paper)

- Unbounded-horizon / arbitrary-n correctness (explicitly future work).
- Multi-machine clock behavior (single-host experiments only).
- Performance/scalability (T0 forbids; scale story is failure→repair,
  not scaling evidence; 20-robot W-HEAL is liveness-under-heal, not
  throughput).
- Transport mechanism findings (hypothesis downgraded; micro R/B void
  for causal inference; RTPS meta-traffic unavailable).
- Immediate physical compliance with new zones (§G.5).
- Any B3-class comparison (never implemented; §F is conceptual).
- Adversarial-content robustness beyond I2/I2B mutation tests.

## 3. SCOPE-contamination check (required)

`efrs-t12/docs/EFRS_NOVELTY_BOUNDARY.md` carries SCOPE-project
content: sensor-coordinate censor OPERATORS, leave-family-out SENSOR
DEGRADATION, HardGeneric comparator, domain-randomization fallback,
and the 2026 hard-bank scenario-mining discussion — all unrelated to
fleet rule synchronization (different project: sensor corruption
robustness). FINDING: the file mixes two projects' novelty claims.
Any EFRS publication must cite/scoping-filter this file and must NOT
inherit SCOPE claims (operator mining, degradation envelopes,
masked-training comparisons). This P0 series contains zero SCOPE
content (verified: no SCOPE terms in any EFRS_P0 document). The T0
novelty boundary (`efrs-t0/...`) and the candidate claim (§E) are
SCOPE-free; the T12 file needs a scoping note if ever cited.

## 4. Amendment hygiene (supports G4)

Original FAILs retained (T1, T1.1-STOP, T1.2-FAIL, M-original,
A3-broken, N-original); validity ledger labels purposes without
altering raw JSON; A3 + restart amendments diff-audited; ORDER
DEVIATION disclosed with post-hoc code-identity proof. No concealed
rerun, no overwritten record found in the sampled chain.
