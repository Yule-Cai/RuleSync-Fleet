# EFRS-T1.3a Interim Report — Workload-Semantics Correction Round

Date: 2026-10-14. Freeze `2680322`. No M/N/Q per authorization. All
forbidden items untouched (queue depth, QoS, deadline, retry, lease,
B_real, fault durations, quorum, protocol state machine —
`efrs_ros2/` verified byte-identical to the T1.3 freeze).

## 1. Finding implemented (prereg §1)

`loss_random.until` never fired in any T1→T1.3 runner (permanent arm,
no disarm). Fix: `until` schedules an independent per-fault disarm;
no-`until` stays permanent. Shared `sched_util.fault_end` + GST math.
GST fail-fast + `workload_valid`/`workload_reason`/`gst` in every
record (no-faults→valid; no-finite-gst→invalid; post-gst-fault→invalid;
elapsed<GST→invalid; else valid gst-reached).

## 2. Tests (all green pre-freeze, local + frozen container)

14 pure proofs: msgspec/shim/wal/txn/WAL-abort/depth/source-contracts/
ledger-schema/QoS-contracts + T1.3a expiry-independence (`until`
honored exactly; overlapping losses independent), permanence
(no-`until` → +∞), GST math (W-HEAL file → 248.02; W-SUSTAINED keeps
≥1 unterminated loss), AST branch contract (disarm scheduled).
Live disarm probe (untracked smoke, pre-freeze validation): epoch 2
proposed into 50% loss aborted then committed post-clear; record
marked GST=7.0 gst-reached.

## 3. W-HEAL re-run (byte-identical sched, fixed runner)

Domain 168, 600 s cap, 20 robots, GST=248.02, workload_valid=true.
- **100/100 distinct epochs committed, 100 issued.**
- 3 aborts total (vs 51 in the void run); attempts/update 1.0 for all
  100 (no update needed more than its first attempt... precisely:
  106 PREPARE broadcasts ≈ 100 + 6 reattempt-related; every committed
  update took ≤2 attempts).
- Heal-to-commit (heal-straddling pairs): max **2.06 s**, p50 1.22 s
  (≤10 s bound with margin).
- Propose→commit: max 5.01 s (ep 73, fault window + abort cycle),
  p50 0.13 s, p95 0.15 s.
- Stale_max 263.2 ms (< B_real); 0 mismatches/rollbacks/unreconciled;
  274 fence rejections; invalid_lease 0.
- Ledger: 20/20 ledgers, 31,989 rows, 6,059 ACCEPTs, all four F1
  counters 0, 0 unverifiable (`gate_ok: true`).
- Traffic/shape vs void run: 106 PREPARE + 100 COMMIT broadcasts
  (vs T1.1-era flood rates); 2,036 votes received; 0 redrives
  (deleted), 0 retransmits (deleted).
- Resources: CPU ~160–269% descriptive; RSS ratio 1.03 (2006→2066 MB,
  gate ≤1.25 PASS). Absolute 2 GB level unexplained but bounded and
  flat post-warmup (T1's 400 MB reading was startup-phase only and is
  not a valid steady-state comparator — recorded correction).

## 4. Micro R/B re-runs (1x each, diagnostic only)

- R2 (frozen T1.2 RELIABLE + permanent 20% loss): 2/8 commits,
  9 aborts — replicates permanent-loss stall. (No workload_valid
  field exists in T1.2 records; interpreted as sustained-loss stress
  by construction.)
- B2 (T1.3a BEST_EFFORT + healing 3 s loss): **8/8 commits**,
  1 abort, stale 149.5 ms, workload_valid gst-reached (GST=8.0).
- Interpretation (no overclaim): workloads differ by runner
  generation (R permanent vs B healing), so transport is NOT isolated
  by this pair. B demonstrates designed recovery (mostly gen-0
  commits post-heal; BEST_EFFORT vote path functions). R replicates
  the expected permanent-loss stall. Mechanism (ACKNACK implosion)
  remains hypothesis.
- Stronger transport evidence (observational, not controlled):
  W-HEAL under BEST_EFFORT sustained 2,036 received votes + 100
  commits over 600 s with healing faults; the void RELIABLE run
  managed 1,536 votes/274 s then ~zero. Direction supports the
  hypothesis; proof of mechanism still requires DDS-level data.

## 5. What did NOT run (per authorization)

W-SUSTAINED re-run (permanence proven by tests; workload unchanged).
K13 re-run (no loss_random involved; T1.3 evidence stands).
M/N/Q (awaiting direction).

## 6. Deviations

- Analysis scripts (`t13a_heal_analyze.py`) iterated twice (clock
  anchor bug: absolute vs elapsed mixing gave 144,457 s; fixed with
  first-attempt anchor; verified 2.06 s). Read-only tooling.
- `ros2 topic info -v` live QoS capture missed twice (containers exit
  before exec windows). R proven by frozen source (int depth =
  default RELIABLE profile) + B proven by source + runtime
  `txn_qos` proofs + behavior. Triple-redundant capture still
  available opportunistically during any future formal run.
- ACK counts unavailable (D4 evidence-only, no coordinator log
  line) — pre-existing instrumentation gap, carried forward.

## 7. Recommendation

T1.3a correction VERIFIED: healable W-HEAL goes 100/100 with full
ledger cleanliness and bounded recovery. Await lead on: (a) whether
W-HEAL + micro + ledger evidence suffices to retire the T1.2
transport hypothesis in favor of workload-semantics as the primary
explanation (with the depth-48 question downgraded to open); (b) M/N/Q
sequencing; (c) whether the void T1.2/T1.3 records need any further
marking (left untouched per rule 1).
