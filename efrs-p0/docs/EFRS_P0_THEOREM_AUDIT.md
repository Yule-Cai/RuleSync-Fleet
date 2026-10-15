# EFRS-P0 Theorem Audit (time points, bound, assumptions, status)

## 1. Formal time points (per robot, per superseding commit)

- T_c: authoritative COMMIT = coordinator `wal_commit` append
  (monotonic-ns recorded), before COMMIT publish.
- T_r: last renewal at the obsolete epoch = max over same-currency
  RENEW applies + COMMIT-grant time at old currency. No renewal at
  obsolete currency exists after T_c (contact-sync: coordinator
  renews at new epoch; obsolete renews ignored; newer renews pull).
- T_e: local lease expiry = agent `lease_deadline_ns` (steady clock).
- T_s: last stale-motion ACCEPT under the obsolete epoch.
- T_h: first safe HOLD = state tick with holding=true (unreconciled
  or lease-expired) as observed by the fence (next decision HELD).
- T_k: reconciliation completion = reconcile_rep applied (or
  same-currency RENEW for healed non-restarted robots).

## 2. Stale-execution bound derivation (as far as it goes)

ACCEPT under obsolete epoch e requires (gate conjunction):
committed==e (adopted), live lease, reconciled, not holding.
After T_c: adoption of e is impossible (fence/hash/epoch guards +
idempotent-same only); renewal at e is impossible (T_r ≤ T_c side).
Hence the lease covering any post-T_c ACCEPT under e was granted no
later than T_c, expiring ≤ T_c + 1000 ms. Fence evaluates each
command within its 50 ms scheduling budget; in-flight/actuator drain
is budgeted 250 ms. Therefore T_s ≤ T_c + 1000 + 50 + 250 = T_c +
B_real (1300 ms). Measured: stale_max 181.3 ms (matrix/30x),
263.2 ms (W-HEAL), ≤552 ms cell maxima (M) — all inside B_real with
≥2.3x margin; positive control A3 (7792 ms) proves the metric fires
when the mechanism is removed.

## 3. Required assumptions (each load-bearing)

A1 Clock monotonicity (local steady clock; no cross-node sync needed
for safety — expiry is per-robot local). Remove ⇒ lease meaningless;
bound REFUTED. Untested across machines (single-host experiments).
A2 Bounded fence scheduling (≤50 ms per decision). Remove ⇒ stale
ACCEPTs can overshoot T_e arbitrarily; bound CONDITIONAL on it.
Measured consistent, never stress-proven.
A3 Bounded command-to-actuator drain (≤250 ms in-flight). Remove ⇒
physical motion outlives authorization arbitrarily. Empirical only.
A4 Coordinator authority honesty (single coordinator sends one
ruleset per epoch; no equivocation). Remove ⇒ I2 unenforceable by
followers alone. Outside all fault lists (I2 vacuous in T0 model).
A5 Persistent-state integrity (WAL fsync ordering; atomic robot
state file). Remove ⇒ rollback/resurrection (the I1/I6 class).
Assumed of the filesystem; crash-during-write untested.
A6 Crash/restart behavior = code path (restart ⇒ UNRECONCILED ⇒
hold; coordinator ⇒ fence+1 + single replay). Remove (e.g. state
file deleted, stale WAL replayed by operator) ⇒ I1/I6 open.
A7 No MotionFence bypass (default flags; `--passthrough` /
`--ignore-lease` off). Remove ⇒ no gate (A1/A2 controls demonstrate).
A8 Motion commands actually flow through the fence (deployment
wiring). Remove ⇒ gate vacuous. True in harness + witness
(cmd_vel republish in Phase-K only); deployment-dependent generally.

## 4. Counterexamples on assumption removal (constructive)

- ¬A1 (clock jumps forward): leases never expire ⇒ unbounded stale
  execution; the Kleppmann clock-jump class. (Fencing generations do
  NOT save this: fence only orders adoptions, it does not expire
  currency.)
- ¬A2 (fence starved): ACCEPTs continue past T_e; bound fails open.
- ¬A4 (equivocating coordinator): two robots adopt same epoch with
  different hashes only if verify_rules is bypassed — I2's real
  assumption is verify-enforcement + collision resistance, both
  untested adversarially (I2/I2B mutate payloads in flight; a
  Byzantine coordinator is outside the model).
- ¬A6 (operator replays old WAL): fence_seen persists robotside, so
  replayed COMMITs are rejected — UNLESS robot state files are also
  restored, in which case superseded epochs resurrect. Joint
  backup/restore discipline is assumed, not enforced.

## 5. Five-way distinction (never conflate)

1. Local authorization safety: CONDITIONAL (A1,A2,A7,A8) +
   MODEL-CHECKED ONLY (T0 n=3/horizon-12 exhaustive + TLC 8472 states)
   + EMPIRICAL ONLY at scale (ledgers: 6059 W-HEAL + 483 matrix + 11 N
   + 3 Q ACCEPTs, zero violations). No unbounded proof.
2. Fleet-global epoch consistency (I2): CONDITIONAL (A4 +
   verify-enforcement); T0 coverage vacuous (no content faults);
   ROS I2/I2B EMPIRICAL ONLY (341/230 fence rejections, legitimate
   epochs unaffected).
3. Bounded obsolete-rule execution (I5/B_real): CONDITIONAL (A1–A3)
   + derivation §2 + EMPIRICAL margins. The bound is one lease-cycle
   plus engineering margins — nearly definitional given the mechanism;
   its content is the machinery that keeps it true under
   partition/restart (contact-sync, idempotency, re-fence, pull).
4. Physical stopping latency: EMPIRICAL ONLY (Gazebo egress ≤3.1 s;
   inside-at-commit residuals physically irreducible). No bound
   claimed; never convert authorization bounds into stopping claims.
5. Compliance with newly activated physical constraints: NOT
   established as immediate. Bounded authorization + observed egress
   is the entire claim. It is EXPLICITLY recorded here that bounded
   stale authorization alone does NOT guarantee immediate physical
   compliance with a new KEEP_OUT zone (a robot inside the zone at
   commit needs egress time; 2PC-witness 40.4 s vs EFRS ≤3.1 s is a
   comparison, not a compliance proof).

## 6. Status classifications

- Bounded stale authorization (I5/B_real): CONDITIONAL (assumptions
  A1–A3 explicit; small-instance MODEL-CHECKED; ROS EMPIRICAL).
- Epoch monotonicity + hash binding (I1/I2): CONDITIONAL (A4–A6).
- Gate conjunction (I3), lease-hold (I4), restart/reconnect
  discipline (I6/I7): CONDITIONAL + MODEL-CHECKED (small) +
  EMPIRICAL (matrix/witness/ledgers).
- Unbounded-horizon / arbitrary-n proof: NOT CLAIMED (T0 theorem doc
  says so explicitly). No PROVEN tag is assigned to any theorem in
  this audit. Nothing is REFUTED within the stated assumptions; A3
  refutes only the mechanism-removed variant (as designed).
