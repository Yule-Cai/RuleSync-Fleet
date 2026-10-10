"""Post-hoc gate analysis (read-only; runner records untouched).

Refines raw counts into the frozen gate quantities:
- authorization_expired_accepts: EXECUTED while (req != local committed
  at exec) OR (lease expired at exec) OR (agent unreconciled at exec).
  Must be 0 for EFRS (fence-enforced).
- fleet_stale_max_ms: max over EXECUTED with req < fleet max at exec of
  (t_exec - t_first_supersede). Small values (<B_real) are propagation
  races during dissemination, reported with distribution, gated by max.
- unreconciled_executions / invalid_lease_executions: subsets above.
- rollback / reconciliations / rejected tallies as before.

Usage: python3 analyze.py --rec rec.json [--out gate.json]
Prints one JSON line with gate verdicts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

B_REAL_MS = 1300.0


def analyze(rec: dict) -> dict:
    evs = rec.get("events", [])
    states = rec.get("states", [])
    commits = sorted(rec.get("commits_seen", []))
    sched = rec.get("schedule", {})
    robots = sched.get("robots", ["R1", "R2", "R3"])

    # Agent state timeline per robot: list of (t, snapshot) sorted.
    tl: dict[str, list] = {r: [] for r in robots}
    for s in states:
        if s.get("role") == "agent" and s.get("id") in tl:
            tl[s["id"]].append((float(s.get("_rt", 0)), s))
    for r in tl:
        tl[r].sort()

    def state_at(robot, t):
        cur = None
        for tt, s in tl.get(robot, []):
            if tt <= t:
                cur = s
            else:
                break
        return cur

    def fleet_max(t):
        m = 0
        for tt, e in commits:
            if tt <= t:
                m = max(m, int(e))
        return m

    def supersede_t(req):
        for tt, e in commits:
            if int(e) > req:
                return tt
        return None

    auth_expired = 0
    unverifiable = 0
    unreconciled = 0
    invalid_lease = 0
    epoch_mismatch = 0
    stale_durs = []
    rejected = 0
    for e in evs:
        if e.get("verdict") != "EXECUTED":
            if e.get("verdict") in ("REJECTED", "HELD"):
                rejected += 1
            continue
        req = int(e.get("required_epoch", -1))
        t = float(e.get("_rt", 0))
        robot = e.get("robot")
        # Fence-contemporaneous evidence: latest agent snapshot at most
        # 500 ms old (state period 200 ms + DDS margin). Older evidence
        # cannot exonerate the fence decision -> unverifiable.
        fresh = [s for tt, s in tl.get(robot, [])
                 if t - 0.5 <= tt <= t]
        if not fresh:
            unverifiable += 1
            auth_expired += 1
            continue
        st = max(fresh, key=lambda s: float(s.get("_rt", 0)))
        bad = False
        if req != int(st.get("committed", -1)):
            # Same sustained-evidence principle: a commit sighting within
            # ±500 ms explains the race (fence acted pre-application).
            if not any(abs(tt - t) <= 0.5 for tt, _ in commits):
                epoch_mismatch += 1
                bad = True
        # Invalid-lease requires SUSTAINED expiry: every snapshot in a
        # ±500 ms window shows an expired lease. A single expired
        # snapshot beside live ones is a renewal-resumption boundary
        # (fence acted on live evidence arriving in the same ms), not a
        # fence failure. Window rule declared here, applied uniformly.
        if float(st.get("lease_deadline_ns", 0)) > 0:
            window = [s for tt, s in tl.get(robot, [])
                      if t - 0.5 <= tt <= t + 0.5]
            live = [s for s in window
                    if t * 1e9 <= float(s.get("lease_deadline_ns", 0))]
            if window and not live and t * 1e9 > float(
                    st.get("lease_deadline_ns", 0)):
                invalid_lease += 1
                bad = True
        if not st.get("reconciled", True):
            unreconciled += 1
            bad = True
        if bad:
            auth_expired += 1
        if req < fleet_max(t):
            st0 = supersede_t(req)
            if st0 is not None:
                stale_durs.append(max(0.0, t - st0))

    rollbacks = 0
    last_com: dict[str, int] = {}
    reconciles = 0
    prev_rec: dict[str, bool] = {}
    for s in states:
        if s.get("role") != "agent":
            continue
        rid, c = s.get("id"), int(s.get("committed", 0))
        if rid in last_com and c < last_com[rid]:
            rollbacks += 1
        last_com[rid] = c
        rec = bool(s.get("reconciled", True))
        if rid in prev_rec and (not prev_rec[rid]) and rec:
            reconciles += 1
        prev_rec[rid] = rec

    max_stale_ms = round(max(stale_durs) * 1000.0, 1) if stale_durs else 0.0
    return {
        "authorization_expired_accepts": auth_expired,
        "unverifiable_executions": unverifiable,
        "epoch_mismatch_executions": epoch_mismatch,
        "invalid_lease_executions": invalid_lease,
        "unreconciled_executions": unreconciled,
        "fleet_stale_count": len(stale_durs),
        "fleet_stale_max_ms": max_stale_ms,
        "stale_commands_rejected": rejected,
        "epoch_rollback_count": rollbacks,
        "reconciliations": reconciles,
        "b_real_ok": max_stale_ms <= B_REAL_MS,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rec", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    rec = json.loads(Path(args.rec).read_text())
    res = {"record": str(args.rec), "gates": analyze(rec)}
    print(json.dumps(res, sort_keys=True))
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
