# EFRS-T1.3a A3 Positive-Control Amendment (surgical, lead-authorized)

Date: 2026-10-14. Research-lead decision: APPROVE SURGICAL A3
POSITIVE-CONTROL REPAIR. This amends ONLY the `--old-renewal` test
branch; the production EFRS path, coordinator, fence, QoS, lease,
B_real, scheds, and transaction semantics are untouched (diff-audited
below). The original M-round FAIL (A3 stale 168 ms) remains in the
historical record.

## Original failure

T1.3a A3 (`rec-efrs-A3-A3.json`, ablation flag `--old-renewal`,
fault `loss_commit_keep_renew` t=2.5–9.0): stale_max = 168.0 ms.
T1 A3 (same sched, same flag): stale_max = 7830.8 ms with R3 executing
epoch 1 while the fleet sat at epoch 2 (36 stale samples; R3's log is
238 lines of `old-renewal: lease only, no adopt`, zero adoptions).

## T1 vs T1.3a source comparison (the error)

T1 `robot_agent.on_renew` (frozen, `efrs-t1/.../robot_agent.py:156`):

    if int(d["epoch"]) > st["committed"] and not args.old_renewal:
        ... verify hash ...
        st["committed"] = int(d["epoch"])   # adopt ONLY when NOT old
        ...
    if args.old_renewal:
        log("old-renewal: lease only, no adopt")   # informational
    st["fence_seen"] = ...                        # then unconditional
    extend lease; set reconciled                   # lease extension

T1.3a (broken) `on_renew` under `args.old_renewal`: ADOPTED any newer
epoch (with hash verify) before extending — i.e. it implemented
"adopt + extend", the opposite of the frozen "extend WITHOUT adopt".

## Why the control was wrong

The implementer misread the informational log line ("lease only, no
adopt", which in T1 sits OUTSIDE the adopt guard and fires in both
modes) as describing an adopt-capable path, and reconstructed
"adopt any newer + unconditional extend" as the loose behavior. In
fact the looseness that reproduces the T0 bug is precisely extension
WITHOUT adoption: the robot's old epoch stays live (lease renewed) but
never advances, so obsolete-rule motion continues indefinitely while
contact persists. The corrected branch below mirrors T1 lines 156–175
exactly (modulo unchanged surrounding names).

## Corrected semantics (this amendment)

Under `--old-renewal`, on a newer-epoch RENEW: do NOT adopt the newer
epoch/hash (committed/hash/prepared untouched, nothing persisted);
continue extending the OLD epoch's lease; preserve the loose
reconcile behavior. Everything else in `on_renew` (fence gate, normal
EFRS path, reconcile-pull, obsolete-ignore) is unchanged.

## Regression tests (new, must pass pre-execution)

- `test_old_renewal_never_adopts`: model-level Sim with the T1.3a
  checker is protocol-code, not agent-code; instead the test asserts
  on the ROS source: the `old_renewal` branch contains no assignment
  to `st["committed"]`/`st["hash"]` (AST), while the normal path
  retains exactly one guarded adoption site.
- `test_old_renewal_extends_lease`: the `old_renewal` branch still
  extends `lease_deadline_ns` unconditionally (AST: assignment
  present).
- T1-exactness: the corrected branch text-matches T1 lines 156–175
  up to the documented log-string additions (diff quoted in commit).

## Diff audit (required before execution)

`git diff` from the freeze must show ONLY:
`efrs-t13a/efrs_ros2/robot_agent/robot_agent.py` (old-renewal branch),
`efrs-t13a/tests/test_pure.py` (the two tests above), and this doc.
Any other file changed → refuse to execute.
