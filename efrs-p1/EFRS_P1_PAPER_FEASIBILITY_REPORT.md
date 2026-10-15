# EFRS-P1 Paper Feasibility Report (Phase F)

P0 accepted: SYSTEMS_PAPER_CANDIDATE; method novelty NOT established;
CAFA closed. This round used existing evidence only. No ranking claims
are made (no quartile verified or used).

## 1. Contribution verdict (from CONTRIBUTION_MATRIX)

Three B3-honest contributions stand: (C1) lease-and-fence enforcement
stack built/measured/auditable in ROS 2 — explicitly "the combination
was built and measured", not "the combination is new"; (C2)
preregistered fault-injection methodology with retained negatives and
validity-ledger discipline; (C3) measured stale-authorization envelope
plus the authorization/stopping/compliance trichotomy (framing, not
mechanism). Six explicit non-contributions recorded (no new protocol,
no theorem beyond conditional, no scalability, no transport, no
hardware, no B3 comparison).

## 2. Mandatory evidence status (Phase C)

Present and frozen: T0 counterexamples + bounded checks; 480-run
matrix; 5-robot injection; 20-robot eventual-heal 100/100;
permanent-loss fail-safe (237 HOLDs, T1 wedge); MotionFence ledgers
(6059 + 483 + 11 + 3 ACCEPTs joined, zero violations); A1/A2/A3
controls (incl. repaired 7792 ms); 3 Gazebo witnesses (+3 2PC);
all amendments/FAILs retained with validity labels. P0 limitations
and unsupported claims imported unchanged (§8 of P0 claim matrix).
Disclosed everywhere it matters: 20-robot runs are lightweight ROS 2
processes on one host, not 20 physical robots; physics is Gazebo-only.

## 3. Venue feasibility (verified 2026-10-15; scopes + costs)

| Venue | Fit | Verified scope/cost facts |
|---|---|---|
| IEEE RA-L | PRIMARY FIT | Scope incl. "application case studies" and "innovative ideas"; 6 pp (+2 extra); hybrid: OA APC $2,800 (2026) or traditional no-APC route; ~4–6 mo decision; RA-L→ICRA presentation option. 6 pp forces a tight C1–C3 story; supplements via multimedia welcome. |
| IEEE RAM (regular technical article / R-article) | FIT (alternative) | "Focus on working systems", practicing engineer; ≤9 magazine pp (~4500 words), ≤20 refs, ≤10 eqs; reproducibility (R-article) track matches ledger/artifact strengths; OA $2,045; still requires "novel and high significance" — R1 risk applies. |
| ICRA / IROS (contributed paper) | FIT (conference route) | 8 pp incl. refs (ICRA 2026 verified); archival proceedings, no APC (registration ≈ €825 early-member + travel); systems-with-experiments papers routinely accepted; RA-L→conference presentation option also exists. Next-cycle deadlines apply (ICRA 2026 submission closed Sep 2025). AI-screening policy noted for manuscript prep. |
| IEEE T-RO | OUT (bar) | "Major advances … fundamental papers"; bar incompatible with P0 (novelty not established). 18 pp, hybrid $2,800 + overlength beyond 12 pp. |
| JFR | OUT (rule) | Validation policy bars simulation/controlled-lab-only work ("will not publish articles in which the experimental validation is restricted to simulation or controlled laboratory experiments"). EFRS is Gazebo + single-host lab. Do not submit. |
| Field Robotics (new, green OA, no fees) | OUT (rule) | Same simulation/lab-only exclusion as JFR. Do not submit. |
| NSDI Operational Systems Track | EXCLUDED | Per lead instruction: not recommended on simulated fleet experiments alone. |

Costs (verified): RA-L OA $2,800 vs traditional $0 (+$175/overlength
page beyond 6, max 8); RAM OA $2,045; T-RO OA $2,800; ICRA ≈ €825–1,160
registration + travel, no APC. Non-OA routes exist at all IEEE hybrids
(review indifferent to OA choice).

## 4. Decision

**SYSTEMS_PAPER_WORTH_WRITING** — with venue lock and framing lock:
(a) venue RA-L primary (ICRA presentation option), RAM alternate;
JFR/Field-Robotics/T-RO explicitly out; (b) framing locked to C1–C3
with B3-first related work, trichotomy enforced in every section,
and the unsupported-claim absence table; (c) no new fundamental-
algorithm claim anywhere (positive verdict does not depend on one).
Dominant residual risk: an R1-strong panel rejects on B3-equivalence
despite evaluation depth — estimated the likeliest failure mode;
mitigation is venue choice + R3-strength artifacts, not rebuttal.
Secondary risk: R2-grade safety reading if any sentence overclaims
stopping/compliance — mitigated by the trichotomy discipline plus
the explicit lightweight-process disclosure.

## 5. Exact remaining work (writing only; no experiments authorized)

1. Draft the 6-page RA-L manuscript per PAPER_OUTLINE (B3-first
   related work; assumption box A1–A8; absence table; artifact
   appendix pointer).
2. Cost appendix (hosts, node counts, runtimes) for reproducibility.
3. SCOPE-quarantine pass over every citation of the T12 boundary file.
4. Pre-submission self-review against MOCK_REVIEWS fatal triggers
   (novelty verbs; compliance sentences; venue mismatch).
NOT authorized here: hardware trials (would address R2-fatal, needs
lead approval + new preregistration); B3 implementation (would invite
superiority claims the story must not make); any new fault schedule
or benchmark.
