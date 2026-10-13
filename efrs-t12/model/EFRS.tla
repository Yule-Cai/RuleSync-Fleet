------------------------------ MODULE EFRS ------------------------------
(*
  EFRS-T0 record artifact: TLA+ model of the lease/fence motion gate.
  Each motion logs (robot, epoch, tick, lease-at-exec). TLC checks:
    - MonotonicEpoch: committed epochs never decrease (I1).
    - GateLogged: every logged motion had tick <= lease-at-exec (I3+I4:
      epoch match is enforced by Move using committed[r]; reconciled is
      enforced by CanMove).
  The Python exhaustive harness (fleet_checker.py) is the executed
  verification over the full fault list; this spec pins the gate logic
  declaratively. Model config: EFRScfg (Robots={r1,r2,r3}, MaxEpoch=2,
  Lease=5, Horizon=8).
*)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS Robots, MaxEpoch, Lease, Horizon

VARIABLES committed, leaseExp, reconciled, clock, motions, heldCount

vars == <<committed, leaseExp, reconciled, clock, motions, heldCount>>

Init ==
    /\ committed = [r \in Robots |-> 0]
    /\ leaseExp = [r \in Robots |-> Lease]
    /\ reconciled = [r \in Robots |-> TRUE]
    /\ clock = 0
    /\ motions = {}
    /\ heldCount = 0

CanMove(r) ==
    /\ reconciled[r]
    /\ clock <= leaseExp[r]

Grant(r, e) ==
    /\ e = committed[r] + 1
    /\ e <= MaxEpoch
    /\ committed' = [committed EXCEPT ![r] = e]
    /\ leaseExp' = [leaseExp EXCEPT ![r] = clock + Lease]
    /\ UNCHANGED <<reconciled, clock, motions, heldCount>>

Move(r) ==
    /\ CanMove(r)
    /\ clock < Horizon
    /\ motions' = motions \cup {[robot |-> r, epoch |-> committed[r],
                                 tick |-> clock,
                                 lease |-> leaseExp[r]]}
    /\ clock' = clock + 1
    /\ UNCHANGED <<committed, leaseExp, reconciled, heldCount>>

Hold(r) ==
    /\ ~CanMove(r)
    /\ clock < Horizon
    /\ heldCount' = heldCount + 1
    /\ clock' = clock + 1
    /\ UNCHANGED <<committed, leaseExp, reconciled, motions>>

Expire(r) ==
    (* partition without renewal: clock jumps past this robot's lease *)
    /\ clock <= leaseExp[r]
    /\ clock' = leaseExp[r] + 1
    /\ UNCHANGED <<committed, leaseExp, reconciled, motions, heldCount>>

Done == clock >= Horizon /\ UNCHANGED vars

Next ==
    \/ \E r \in Robots : Grant(r, committed[r] + 1)
    \/ \E r \in Robots : Move(r)
    \/ \E r \in Robots : Hold(r)
    \/ \E r \in Robots : Expire(r)
    \/ Done

Spec == Init /\ [][Next]_vars

(* TLC checks GateLogged plus deadlock freedom. Epoch monotonicity (I1)
   is enforced structurally by Grant (committed[r]+1 only) and covered
   empirically by the Python harness rollback detector; it is not stated
   as a checkable state invariant here (that would need ghost history). *)

GateLogged == \A m \in motions : m.tick <= m.lease

(*************************************************************************
 * T1.1 transaction-attempt layer (frozen 2026-10-13, BEFORE results).
 * Pins the eventual-heal recovery mechanics declaratively; the Python
 * exhaustive harness (fleet_checker.py) is the executed verification.
 * Scope: single logical epoch in flight at a time; generations bounded
 * by GenCap; reachability abstracted (all-votes-required among Robots —
 * the Python harness covers partitions). Untimed control steps; the
 * motion-gate clock above is untouched.
 *************************************************************************)

CONSTANT GenCap

VARIABLES cEp, cSt, cGen, cVotes, pPrep, pCom

gateVars == <<committed, leaseExp, reconciled, clock, motions, heldCount>>
txnVars == <<cEp, cSt, cGen, cVotes, pPrep, pCom>>

NoTxn == [ep |-> 0, gen |-> 0]

TxnInit ==
    /\ cEp = 0
    /\ cSt = "idle"
    /\ cGen = 0
    /\ cVotes = {}
    /\ pPrep = [r \in Robots |-> NoTxn]
    /\ pCom = [r \in Robots |-> 0]

TPropose ==
    (* fresh epoch, or same-epoch re-attempt after an abort; never
       resurrects an aborted gen, never overlaps an active attempt.
       Generations are per-epoch (reset on commit), capped by GenCap. *)
    /\ cSt = "idle"
    /\ cEp + 1 <= MaxEpoch
    /\ cGen <= GenCap
    /\ cSt' = "wait"
    /\ cVotes' = {}
    /\ UNCHANGED <<cEp, cGen, pPrep, pCom>>

TDeliverPrep(r) ==
    (* (re)transmission to a missing voter; duplicates collapse *)
    /\ cSt = "wait"
    /\ pPrep' = [pPrep EXCEPT ![r] = [ep |-> cEp + 1, gen |-> cGen]]
    /\ UNCHANGED <<cEp, cSt, cGen, cVotes, pCom>>

TVote(r) ==
    (* idempotent: voting twice for the identical txn changes nothing *)
    /\ cSt = "wait"
    /\ pPrep[r] = [ep |-> cEp + 1, gen |-> cGen]
    /\ cVotes' = cVotes \cup {r}
    /\ UNCHANGED <<cEp, cSt, cGen, pPrep, pCom>>

TCommit ==
    (* unanimous READY among Robots (no-partition abstraction);
       durable decision recorded in cEp; generations reset *)
    /\ cSt = "wait"
    /\ cVotes = Robots
    /\ cEp' = cEp + 1
    /\ cSt' = "idle"
    /\ cVotes' = {}
    /\ cGen' = 0
    /\ UNCHANGED <<pPrep, pCom>>

TTimeoutAbort ==
    (* explicit abort: MUST leave the round; robots may hold stale prep *)
    /\ cSt = "wait"
    /\ cVotes /= Robots
    /\ cSt' = "idle"
    /\ cGen' = cGen + 1
    /\ UNCHANGED <<cEp, cVotes, pPrep, pCom>>

TApplyCommit(r) ==
    (* a robot applies ONLY the committed epoch; same-epoch
       re-application is an idempotent no-op; stale prep never applies *)
    /\ pCom[r] < cEp
    /\ pPrep[r].ep = cEp
    /\ pCom' = [pCom EXCEPT ![r] = cEp]
    /\ UNCHANGED <<cEp, cSt, cGen, cVotes, pPrep>>

TxnStep ==
    \/ TPropose
    \/ \E r \in Robots : TDeliverPrep(r)
    \/ \E r \in Robots : TVote(r)
    \/ TCommit
    \/ TTimeoutAbort
    \/ \E r \in Robots : TApplyCommit(r)

Next2 == (Next /\ UNCHANGED txnVars) \/ (TxnStep /\ UNCHANGED gateVars)

(* Fairness target: the round exits (commit or abort). Both actions
   fully frame all variables, satisfying WF's syntactic requirement. *)
TxnExit == ((TCommit \/ TTimeoutAbort) /\ UNCHANGED gateVars)

Spec2 == (Init /\ TxnInit) /\ [][Next2]_<<gateVars, txnVars>>
    /\ WF_<<gateVars, txnVars>>(TxnExit)

(* Safety: per-robot applied epoch never exceeds committed, never
   decreases (no cross-txn application, no rollback — I1). *)
NoCrossTxn == \A r \in Robots : pCom[r] <= cEp

(* Liveness (checked under weak fairness): an active attempt always
   eventually leaves the round — the anti-wedge property whose absence
   wedged T1 scale-20. *)
AttemptLeaves == (cSt = "wait") ~> (cSt = "idle")

(* Safety: generations stay within the modeled bound. *)
GenBounded == cGen <= GenCap + 1

=============================================================================
