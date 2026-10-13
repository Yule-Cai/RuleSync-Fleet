# EFRS-T1.1 Liveness Contract (conditional claim boundary)

Date: 2026-10-13. Research-lead authorized. This contract bounds what
T1.1 may claim. It does not modify any T1 safety semantic.

## What EFRS does NOT guarantee

EFRS does not guarantee progress under a permanent partition. The
following words MUST NOT appear in any T1.1 claim, report, or title:

- universally non-blocking
- partition-tolerant commit progress
- guaranteed progress under arbitrary communication failure

## Required assumption: EVENTUAL HEAL

There exists a time GST (Global Stabilization Time) after which all
participants required for a rule update are alive/recovered, mutually
reachable, and transaction messages are eventually delivered.

Concretely for the experiment suite: every fault schedule that carries
a liveness expectation MUST contain a finite fault window followed by
a heal instant H; all liveness measurements start at max(H, GST). A
schedule with no heal carries NO commit expectation (safety-only:
bounded stale execution + correct HOLDs, as demonstrated by T1
scale-20).

## Claim to test (conditional liveness)

After EVENTUAL HEAL, a pending logical hard-rule update eventually
reaches COMMIT or an explicit terminal ABORT, and future updates are
not blocked by stale transaction state.

Operationalized for the suite: after heal, committed progress is
required — the pending logical update commits (or aborts terminally
with the round left, never wedged), attempts advance with fresh
attempt generations, and no later update is blocked by superseded
transaction state. Retry attempts do not count as new logical updates.

## Unit of progress

The unit of progress is the COMMITTED LOGICAL HARD-RULE UPDATE, not
the proposal count. The T1 scale failure mode (100 proposals, 0
commits counted as anything but failure) must be unrepeatable as a
reported success: a run with proposals but no commits is a liveness
failure, however clean its safety counters.

## Safety/liveness separation

- The safety theorem (bounded stale-rule execution ≤ B_real = 1300 ms
  under the modeled failures, I1..I7) and the conditional liveness
  claim are SEPARATE statements with separate gates. Safety evidence
  from T1 is preserved but, because coordinator transaction code
  changes, the full 3-robot safety regression must re-pass on the
  final T1.1 implementation (§O).
- A halted fleet with zero stale motion is correct fail-safe behavior,
  not liveness success. Liveness success requires commits after heal.

## Inherited timeouts (unchanged from T1 preregistration)

- Prepare attempt deadline: 1500 ms (unchanged; NOT lengthened).
- PREPARE retransmission period: the existing frozen heartbeat/contact
  period (100 ms coordinator RENEW broadcast). No new tuned period.
- Post-abort re-attempt delay: exactly one heartbeat/contact period.
- Recovery timeout (heal-to-commit bound): **10 s**, inherited
  unchanged from the T1 preregistration (`recovery_timeout (liveness)
  = 10 s`); reconciliation_timeout = 5 s likewise inherited. These
  values predate all T1.1 results and are not fitted to observations.
- Derivation of 10 s against T1.1 mechanics: one 1500 ms attempt window
  + abort dissemination (≤1 heartbeat period) + one heartbeat-period
  re-attempt delay + one full successful attempt (≤1500 ms incl.
  retransmissions) + one COMMIT dissemination/ACK cycle + scheduling
  allowance on a loaded box. The bound is generous by construction;
  any systematic approach of the bound is itself a finding.

## Forbidden weakenings (restated from authorization §C)

Majority quorum; skipping unreachable robots; extending leases to gain
votes; committing to only reachable robots; weakening MotionFence;
changing B_real; renewing a stale epoch; Raft/Paxos/consensus addition.
The commit threshold semantics are EXACTLY the T0 rule: commit iff
every reachable-participant vote required by the frozen rule is READY
— reachability determined as in T1, and an incomplete round must ABORT
explicitly and leave the round (never wedge).
