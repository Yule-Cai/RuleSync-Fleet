# Reviewer Risk Report (EFRS RA-L Draft V0) + Internal Review

Internal review conducted from three roles. Verdicts are independent;
readiness is NOT auto-concluded (see §4).

## 1. Distributed-systems reviewer

Fatal: (a) B3-equivalence stands unrefuted — recommends reject if the
venue demands architectural novelty; our B3-first framing is correct
but does not remove the objection. (b) I5-as-lease-expiry will read
as definitional; the bound derivation must stay labeled
engineering-budget, which it is.
Fixable: (a) "protocol guarantees" verb check — draft uses
"assembly enforces"; a single slip would be fatal; grep found zero
novelty verbs. (b) Falsifier criterion present (§II). (c) DAS drafts
cited with status before a reviewer finds them — done.
Role verdict: REJECT-on-novelty-grounds at selective venues;
out-of-scope objection at RA-L/RAM-systems if evaluation carries.

## 2. Robotics-safety reviewer

Fatal: (a) any compliance/stopping overclaim — draft enforces the
trichotomy in abstract, §IV, §VI, §VII, and all four figure captions;
"reported, not bounded" for egress. (b) No hardware — disclosed in
abstract, §V, §VII ("no hardware validation").
Fixable: (a) HOLD-as-flag vs HOLD-as-safety: draft states safe-stop
event + latched reason; a reviewer may still ask for measured stop
behavior — Gazebo stop data not in evidence; CANDIDATE fix: one
sentence clarifying HOLD commands zero velocity (harness config,
T1 witness "fenced zero-velocity") — already implied; make explicit
in revision if lead agrees (currently implied only).
Role verdict: WEAK-ACCEPT as systems evaluation; REJECT as safety
paper (correctly — draft does not present as one).

## 3. Applied-systems reviewer

Fatal risks: (a) venue mismatch (JFR-style) — avoided by RA-L
targeting, recorded. (b) Weak-baseline discount ("beats 2PC" heavily
discounted) — draft leans on absolute envelope + controls +
negatives; no B3-superiority language (grep verified).
Fixable: (a) artifact appendix pointer present (frozen schedules,
ledgers, scripts); host specs/runtimes partially present (CPU/RSS in
results; full host spec absent — CANDIDATE addition for revision).
(b) Absence table ("we do not claim X") is distributed, not
tabulated — CANDIDATE revision: single table.
Role verdict: BORDERLINE WEAK-ACCEPT; evaluation depth is the
carrying asset.

## 4. Readiness assessment (not auto-pass)

READY-FOR-LEAD-REVIEW (not ready-for-submission): the draft is a
complete, honest, self-contained 5-page account with all audit items
closed except two candidate revision items (HOLD zero-velocity
explicitness; host-spec appendix line) and one structural option
(absence table). No fatal concern was found that rewording alone
cannot address EXCEPT the venue-relative R1 novelty objection, which
is intrinsic to the work (P0-accepted) and must be carried as
residual risk, not fixed in prose. Submission requires explicit
research-lead authorization (not given).

## 5. Material publication limitations (aud
...[truncated 911 chars]