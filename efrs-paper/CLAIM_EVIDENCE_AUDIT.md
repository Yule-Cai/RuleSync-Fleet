# Claim–Evidence Audit (EFRS RA-L Draft V0)

Method: every numeric or factual claim in main.tex traced to its
frozen source. No new statistics. Status: PASS with two notes (N1, N2).

## Numeric claims

| # | Claim (location) | Source | Verdict |
|---|---|---|---|
| 1 | Stale to 12.7 s (2PC), abstract + VI | T1 report: 2PC F6/F7/F11/F13 7.9–12.7 s | PASS |
| 2 | 40.4 s Gazebo drive-through, abstract + VI | T1 report: wit-2pc stale_max 40.4–40.5 s; 95 in-zone samples | PASS |
| 3 | 480-run matrix (16 faults ×30) | T1 report §matrix; aggregate.py 48/48 cells | PASS |
| 4 | W-HEAL 100/100 (100 issued), 3 aborts, ≤2 attempts | T13a interim §3 + final §8-11 | PASS |
| 5 | 106 PREPARE ≈1.06/update; 100 COMMITs; 2036 votes; 0 redrives/retransmits | Interim §3 ("≈100 + 6 reattempt-related"); final §8-11 | PASS — interim reconciliation adopted verbatim; "attempts/update 1.0" rounding NOT copied (audit item I) |
| 6 | Heal-to-commit max 2.06 s, p50 1.22 s vs 10 s | Interim §3 | PASS |
| 7 | W-HEAL stale 263.2 ms; 31,989 rows; 6,059 ACCEPTs; 20/20 ledgers | Interim §3; final §8-11/§12 | PASS |
| 8 | W-SUSTAINED 2/100; 51 aborts/48 reattempts; 150.0 ms; 1991 rows; 1632 ACCEPTs | Final §7 | PASS |
| 9 | M 480/480 gate_ok; cell maxima 0–552 ms | Final §14 | PASS |
| 10 | Matrix stale 153.8 ms; 30x 181.3 ms; 5-robot 163.1 ms | T1 report §§matrix/30x/5-robot | PASS |
| 11 | A1 31 / A2 32 accepts | T1 report §ablations | PASS |
| 12 | A3 7830.8 ms (T1) / 7792.2 ms (corrected); 214 unadopted renewals; 36 samples; ledger 189/189 | T1 decision + T13a final §17 | PASS |
| 13 | Restart +0.18 s; stale 58.6 ms; 234/234; 8/11 | Final §15 | PASS |
| 14 | I2 341/230 rejections; stale 41/89 ms; commits [1]/[1,2] | Final §16 | PASS |
| 15 | Q 112–113 HELDs; egress ≤3.1 s; detour y→−1.5; stale 58–130 ms; ledgers clean | Final §18 | PASS (counts omitted where Q text gives triplets; "join clean" only) |
| 16 | T0: 9 sched + 400 fuzz/protocol; worst 1 vs bound 5; TLC 8472 states | T0 baseline comparison + theorem docs | PASS |
| 17 | B_real = 1000+50+250 = 1300 ms; vote timeout 1500 ms | T1 prereg + T1 report | PASS |
| 18 | REACH 2000 ms; heartbeat 100 ms; COMMIT lease 1000 ms | coordinator.py L115/363/291; agent default lease 1000 | PASS (code-read) |
| 19 | Scale wedge: 13/20 votes, 99 proposes, 265 s, 237 HOLDs | T1 report §scale + T1 decision | PASS |
| 20 | GST 248.02; propose→commit max 5.01 s (ep 73), p50 0.13, p95 0.15; 274 fence rejections | Interim §3; final §8-11 | PASS |
| 21 | CONTROL_DEPTH max(32,2N+8) | Final §3 | PASS |
| 22 | 41-node discovery storm | 1+20+20 processes, T1 decision | PASS |
| 23 | Partition t=2→25 s; propose t=5 s; zone x∈[4,8], y∈[0,2] | T1 report §witness | PASS (Fig.4 labeled T1 origins) |
| 24 | "Resource ratios near unity" | Final §8-11 RSS 1.03 | PASS (vague-by-design; exact figure in audit only) |

## Non-numeric factual claims

- T0 theorem status "preliminary/bounded": T0 theorem doc verbatim. PASS.
- DAS drafts status (individual, unreviewed, not adopted): datatracker pages verified 2026-10-15 (P0). PASS.
- RA-L format facts (6 pp, hybrid, no minimum): RAS pages verified (P1 Phase E). PASS.
- No-minimum-page-length reliance: T-RO FAQ "no minimum page length in any RAS Journals" (P1). Draft is 5 pp; recorded, not hidden (N1).
- B3 never implemented/evaluated: true by construction (conceptual only, P0 §F). PASS.
- SCOPE quarantine: T12 file mixes projects (P0 claim matrix §3); manuscript contains zero SCOPE content (grep). PASS.
- CAFA absent from manuscript (grep). PASS.

## Notes

N1. Page count is 5, not 6. Complete account fits 5 pages under the
6-page ceiling; padding refused. RA-L has no minimum. Flagged openly
here and in provenance.
N2. Fig.4 mixes T1 time origins with T13a bounds; labeled in caption
and figure-source docstring. Acceptable with label; a picky reviewer
may ask for single-round origins (fixable).
