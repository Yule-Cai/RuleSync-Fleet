"""Deterministic scenario runner: one fault schedule, one record.

Spawns coordinator + N agents + N fences as separate OS processes (real
DDS), settles discovery, executes the schedule (timed faults, restarts,
motion), collects motion_event + state + commit sightings, computes
safety metrics, kills everything, writes the run record JSON.

Usage (inside the frozen container):
  /opt/venv/bin/python fault_harness/runner.py \
      --schedule experiments/sched.json --out experiments/rec.json \
      --domain-id 201 --repo /ws --python /opt/venv/bin/python
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path


def mono_ns() -> int:
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC)


class Runner:
    def __init__(self, sched: dict, out: Path, domain: int, repo: Path,
                 python: str, settle_s: float = 3.0):
        self.sched = sched
        self.out = out
        self.domain = domain
        self.repo = repo
        self.python = python
        self.settle_s = settle_s
        self.workdir = out.parent / (out.stem + "_procs")
        self.procs: dict[str, subprocess.Popen] = {}
        self.spawn_args: dict[str, list] = {}
        self.events: list[dict] = []
        self.states: list[dict] = []
        self.commits_seen: list[tuple] = []
        self.t_start = 0.0
        self.node = None
        self.admin_pub = None
        self.motion_pub = None
        self.cmd_seq: dict[str, int] = {}
        self.last_committed: dict[str, int] = {}
        self.hash_cache: dict[int, str] = {}
        self.timed: list = []

    # ---------- process management ----------
    def _env(self):
        import os

        e = dict(os.environ)
        e["ROS_DOMAIN_ID"] = str(self.domain)
        # APPEND: never clobber the setup.bash ROS paths (rclpy lives there).
        e["PYTHONPATH"] = (str(self.repo) + ":" + e.get("PYTHONPATH", "")
                           ).rstrip(":")
        return e

    def _spawn(self, name, script, args):
        self.spawn_args[name] = (script, args)
        log = open(self.workdir / f"{name}.log", "w")
        p = subprocess.Popen(
            [self.python, str(self.repo / script)] + args,
            env=self._env(), stdout=log, stderr=subprocess.STDOUT)
        self.procs[name] = p
        # Stagger discovery load: simultaneous rclpy.init storms kill
        # spins (observed at 21 nodes; D1-era 4-way abort precedent).
        time.sleep(1.5)
        return p

    def spawn_stack(self, protocol, robots):
        import shutil

        # Fresh workdir every run: stale WAL/state/logs from a previous
        # run at the same path would contaminate initial conditions.
        if self.workdir.exists():
            shutil.rmtree(self.workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / "wal.jsonl").write_text("")
        vote_to = str(self.sched.get("vote_timeout_ms", 500))
        abl = self.sched.get("ablation", None)
        agent_extra, fence_extra = [], []
        if abl == "A1":
            fence_extra = ["--passthrough"]
        elif abl == "A2":
            agent_extra = ["--no-lease-expiry"]
            fence_extra = ["--ignore-lease"]
        elif abl == "A3":
            agent_extra = ["--old-renewal"]
        elif abl is not None:
            raise ValueError(f"unknown ablation: {abl}")
        self._spawn("coordinator", "efrs_ros2/coordinator/coordinator.py",
                    ["--protocol", protocol, "--robots", ",".join(robots),
                     "--wal", str(self.workdir / "wal.jsonl"),
                     "--vote-timeout-ms", vote_to])
        for r in robots:
            self._spawn(f"agent-{r}", "efrs_ros2/robot_agent/robot_agent.py",
                        ["--robot", r, "--protocol", protocol, "--state-file",
                         str(self.workdir / f"state-{r}.json"),
                         "--fleet-size", str(len(robots))] + agent_extra)
            self._spawn(f"fence-{r}", "efrs_ros2/motion_fence/motion_fence.py",
                        ["--robot", r, "--protocol", protocol,
                         "--ledger",
                         str(self.workdir / f"ledger-{r}.jsonl")]
                        + fence_extra)

    def kill_all(self):
        for p in self.procs.values():
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        deadline = time.time() + 5
        for p in self.procs.values():
            try:
                p.wait(timeout=max(0.1, deadline - time.time()))
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def crash(self, name):
        p = self.procs.get(name)
        if p is not None and p.poll() is None:
            p.send_signal(signal.SIGKILL)

    def respawn(self, name):
        script, args = self.spawn_args[name]
        self._spawn(name, script, args)

    # ---------- ROS I/O ----------
    def ros_setup(self):
        import rclpy
        from std_msgs.msg import String

        rclpy.init()
        self.node = rclpy.create_node("efrs_runner")
        self.admin_pub = self.node.create_publisher(String, "/efrs/admin",
                                                    10)
        self.motion_pub = self.node.create_publisher(
            String, "/efrs/motion_cmd", 10)
        self.node.create_subscription(
            String, "/efrs/motion_event",
            lambda m: self.events.append({**json.loads(m.data),
                                          "_rt": time.monotonic()}), 10)
        self.node.create_subscription(
            String, "/efrs/state",
            lambda m: self.states.append({**json.loads(m.data),
                                          "_rt": time.monotonic()}), 10)
        # T1.2 §E + T1.3 §C: /efrs/commit is transaction-control traffic
        # (BEST_EFFORT/VOLATILE/KEEP_LAST at CONTROL_DEPTH). Profile and
        # formula duplicated from rosutil/msgspec (runner cannot import
        # efrs_ros2 from its cwd); equality pinned by test_pure.
        from rclpy.qos import (DurabilityPolicy, HistoryPolicy,
                               QoSProfile, ReliabilityPolicy)
        _cdepth = max(32, 2 * len(self.sched.get("robots", ["R1"])) + 8)
        _cqos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST, depth=_cdepth)
        self.node.create_subscription(
            String, "/efrs/commit",
            lambda m: (self.commits_seen.append(
                (time.monotonic(), json.loads(m.data).get("epoch"))),
                self.hash_cache.__setitem__(
                    int(json.loads(m.data).get("epoch", -1)),
                    str(json.loads(m.data).get("hash", "")))), _cqos)
        # T1.1: transaction observability (attempt/abort/reattempt/commit
        # events from the coordinator; evidence for L/M latencies).
        # Additive; motion_event/state/commits_seen schemas unchanged.
        self.txn_events: list[dict] = []
        self.node.create_subscription(
            String, "/efrs/txn_event",
            lambda m: self.txn_events.append({**json.loads(m.data),
                                              "_rt": time.monotonic()}),
            10)

    def admin(self, payload: dict, repeat: int = 3):
        from std_msgs.msg import String

        for _ in range(repeat):
            self.admin_pub.publish(
                String(data=json.dumps(payload, sort_keys=True)))
            time.sleep(0.02)
            rclpy_spin(self.node)

    def at(self, delay_s: float, fn, label: str):
        self.timed.append((time.monotonic() + delay_s, fn, label))

    def run_timed(self):
        due = [x for x in self.timed if x[0] <= time.monotonic()]
        self.timed = [x for x in self.timed if x[0] > time.monotonic()]
        for _, fn, label in sorted(due):
            try:
                fn()
            except Exception as e:
                print(json.dumps({"fault_error": label, "err": str(e)}),
                      flush=True)

    # ---------- fault mapping ----------
    def F(self, fid, target, action, match=None, params=None):
        return {"fid": fid, "target": target, "action": action,
                "match": match or {}, "params": params or {}}

    def apply_fault(self, f: dict):
        kind = f["kind"]
        A = lambda payload: self.admin({"op": "fault", "fault": payload})
        C = lambda fid, tgt, act, match=None, params=None: A(
            self.F(fid, tgt, act, match, params))
        if kind in ("partition", "partition5"):
            # Star protocol: robots never address peers directly, so any
            # isolate is blocked from everyone on the fault plane. Topology
            # labels stay in the schedule record for the report.
            if kind == "partition":
                members = [f["robot"]]
            else:
                members = sorted({m for g in f["groups"] for m in g
                                  if m != "C"})
            until = f["until"]
            # Bilateral protocol block. Fault plane ONLY (stimulus and
            # evidence planes are harness instrumentation, never faulted).
            pairs = []
            tag = "p5" if kind == "partition5" else "part"
            for r in members:
                for k in ("prepare", "commit", "renew", "reconcile_rep"):
                    fid = f"{tag}-{r}-in-{k}"
                    C(fid, r, "drop", {"msg_kind": k})
                    pairs.append((fid, r))
                for k in ("vote", "state", "reconcile_req"):
                    fid = f"{tag}-{r}-out-{k}"
                    C(fid, r, "drop", {"msg_kind": k})
                    pairs.append((fid, r))
                fid = f"{tag}-C-{r}"
                C(fid, "coordinator", "drop",
                  {"msg_kind": "vote", "robot": r})
                pairs.append((fid, "coordinator"))
                fid = f"{tag}-C-{r}-req"
                C(fid, "coordinator", "drop",
                  {"msg_kind": "reconcile_req", "robot": r})
                pairs.append((fid, "coordinator"))
            heallabel = f"heal-{members}"
            self.at(until - self.elapsed(),
                    lambda: [C(fid, tgt, "clear") for fid, tgt in pairs],
                    heallabel)
        elif kind == "delay":
            tgt = f.get("node", None)
            mk, ms = f["msg_kind"], int(f["ms"])
            match = {"msg_kind": mk}
            if "epoch" in f:
                match["epoch"] = f["epoch"]
            senders = ([tgt] if tgt else self._senders(mk))
            for s in senders:
                C(f"delay-{mk}-{s}", s, "delay_ms", match, {"ms": ms})
        elif kind == "loss_burst":
            mk, until = f["msg_kind"], f["until"]
            for s in self._senders(mk):
                C(f"loss-{mk}-{s}", s, "drop", {"msg_kind": mk})
            self.at(until - self.elapsed(),
                    lambda: [C(f"loss-{mk}-{s}", s, "clear")
                             for s in self._senders(mk)], "unloss")
        elif kind == "loss_random":
            # T1.3a workload-semantics correction: a loss_random WITH
            # until auto-disarms at expiry (independent per fault —
            # no permanent stacking); WITHOUT until it stays permanent
            # (W-SUSTAINED semantics, byte-identical behavior).
            p, seed = float(f["p"]), int(f.get("seed", 1))
            nodes = ["coordinator"] + self.sched["robots"]
            for s in nodes:
                C(f"lossr-{seed}-{s}", s, "drop", {},
                  {"p": p, "seed": seed})
            if "until" in f:
                self.at(float(f["until"]) - self.elapsed(),
                        lambda: [C(f"lossr-{seed}-{s}", s, "clear")
                                 for s in nodes], f"unlossr-{seed}")
        elif kind == "duplicate":
            mk, times = f["msg_kind"], int(f.get("times", 1))
            for s in self._senders(mk):
                C(f"dup-{mk}-{s}", s, "duplicate", {"msg_kind": mk},
                  {"times": times})
            fire_t = float(f.get("t", 0.0))
            self.at(fire_t + 1.0 - self.elapsed(),
                    lambda: [C(f"dup-{mk}-{s}", s, "clear")
                             for s in self._senders(mk)], "undup")
        elif kind in ("crash_coord", "crash_robot"):
            name = ("coordinator" if kind == "crash_coord"
                    else f"agent-{f['robot']}")
            self.crash(name)
            if "restart_at" in f:
                self.at(f["restart_at"] - self.elapsed(),
                        lambda: self.respawn(name), f"respawn-{name}")
        elif kind == "sigstop":
            name = f"agent-{f['robot']}"
            p = self.procs.get(name)
            if p is not None and p.poll() is None:
                p.send_signal(signal.SIGSTOP)
            self.at(f["resume_at"] - self.elapsed(),
                    lambda: self.procs[name].send_signal(signal.SIGCONT)
                    if self.procs[name].poll() is None else None,
                    f"resume-{name}")
        elif kind == "loss_commit_keep_renew":
            until = f["until"]
            targets = [f.get("robot", "R3")]
            for r in targets:
                C(f"f15-{r}", r, "drop", {"msg_kind": "commit"})
            self.at(until - self.elapsed(),
                    lambda: [C(f"f15-{r}", r, "clear") for r in targets],
                    "unf15")
        elif kind == "mutate":
            match = {"msg_kind": f.get("msg_kind", "commit")}
            if "epoch" in f:
                match["epoch"] = f["epoch"]
            C(f["fid"], f.get("node", "coordinator"), "mutate",
              match, {"set": f.get("set", {})})
        elif kind == "drop_gen_votes":
            # T1.2 §K deterministic replay: drop gen-G VOTEs from fixed
            # robots (gen-scoped match, NO until — later generations are
            # structurally unimpaired, which is the timing-independent
            # heal-equivalence; nothing to disarm).
            gen = int(f.get("gen", 0))
            for r in f.get("robots", []):
                C(f"k13-{r}-g{gen}", r, "drop",
                  {"msg_kind": "vote", "txn_gen": gen})

    def _senders(self, msg_kind: str):
        if msg_kind in ("commit", "prepare", "renew"):
            return ["coordinator"]
        if msg_kind == "vote":
            return list(self.sched["robots"])
        return ["coordinator"] + list(self.sched["robots"])

    def elapsed(self):
        return time.monotonic() - self.t_start

    def _wal_epoch(self) -> int:
        import json as _json

        try:
            mx = 0
            with open(self.workdir / "wal.jsonl") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        mx = max(mx, int(_json.loads(line)["epoch"]))
            return mx
        except Exception:
            return 0

    # ---------- motion ----------
    def motion_tick(self):
        from std_msgs.msg import String

        plan = self.sched.get("motion_plan", "honest")
        for r in self.sched["robots"]:
            self.cmd_seq[r] = self.cmd_seq.get(r, 0) + 1
            if plan == "stale":
                req, h = 0, self.hash_cache.get(0, "h0")
            else:
                req = self.last_committed.get(r, 0)
                h = self.hash_cache.get(req, f"h{req}")
            self.motion_pub.publish(String(data=json.dumps(
                {"v": "efrs/1", "cmd_id": f"{r}-{self.cmd_seq[r]}",
                 "robot": r, "required_epoch": req, "required_hash": h,
                 "vx": 0.1, "vyaw": 0.0}, sort_keys=True)))

    # ---------- main ----------
    def run(self):
        import rclpy
        import math as _math

        import sched_util

        protocol = self.sched["protocol"]
        robots = self.sched["robots"]
        # T1.3a GST fail-fast (BEFORE spawning the stack): a schedule
        # that fires any fault strictly after GST refuses to run.
        faults0 = list(self.sched.get("faults", []))
        gst = sched_util.schedule_gst(faults0)
        if gst is not None and gst < _math.inf:
            late = [f for f in faults0
                    if float(f.get("t", 0)) > gst]
            if late:
                raise ValueError(
                    f"post-GST faults refuse to run: {late} (gst={gst})")
        self._gst = gst
        self._fired_fault_times: list[float] = []
        self.spawn_stack(protocol, robots)
        self.ros_setup()
        time.sleep(self.settle_s)
        for _ in range(20):
            rclpy.spin_once(self.node, timeout_sec=0.1)
        self.t_start = time.monotonic()
        fired_propose = set()
        last_motion = 0.0
        duration = float(self.sched.get("duration_s", 12.0))
        truncated = None
        # arm static faults at t=0.. (faults carry absolute t)
        pending = sorted(self.sched.get("faults", []), key=lambda f: f["t"])
        while self.elapsed() < duration:
            try:
                rclpy.spin_once(self.node, timeout_sec=0.05)
            except Exception as e:  # e.g. context shutdown: end run, keep evidence
                truncated = f"{type(e).__name__}: {e}"[:200]
                break
            # track last committed per robot from states
            for s in self.states:
                if s.get("role") == "agent":
                    rid = s.get("id")
                    if rid in robots:
                        self.last_committed[rid] = max(
                            self.last_committed.get(rid, 0),
                            int(s.get("committed", 0)))
            now = self.elapsed()
            while pending and pending[0]["t"] <= now:
                f0 = pending.pop(0)
                self._fired_fault_times.append(float(f0.get("t", 0)))
                self.apply_fault(f0)
            for pr in self.sched.get("proposes", []):
                key = (pr["t"], pr["epoch"])
                if pr["t"] <= now and key not in fired_propose:
                    # Reliable propose: publish, then re-publish at 1 Hz
                    # until the coordinator WAL shows the epoch (covers
                    # post-restart discovery gaps). Verified, not tuned.
                    if self._wal_epoch() >= pr["epoch"]:
                        fired_propose.add(key)
                    else:
                        self.admin({"op": "propose", "epoch": pr["epoch"]})
                        self._last_propose_try = now
            # T1.2 §I sequential logical issue: epochs 1..n_updates,
            # e+1 issued only after e durably COMMITTED (WAL-observed).
            # Retries never count as new updates; no proposal queue.
            if self.sched.get("propose_mode") == "sequential":
                n_up = int(self.sched.get("n_updates", 0))
                issued = getattr(self, "_seq_issued", [])
                we = self._wal_epoch()
                while len(issued) < n_up and we >= len(issued):
                    nxt = len(issued) + 1
                    issued.append((now, nxt))
                    self._seq_issued = issued
                    self.admin({"op": "propose", "epoch": nxt})
                    self._last_propose_try = now
                if (len(issued) < n_up
                        and now - getattr(self, "_last_propose_try", 0)
                        >= 1.0):
                    # Re-drive the pending logical update (idempotent
                    # trigger at the coordinator).
                    self.admin({"op": "propose",
                                "epoch": len(issued)})
                    self._last_propose_try = now
            # re-drive unacknowledged proposes every 1 s
            for pr in self.sched.get("proposes", []):
                key = (pr["t"], pr["epoch"])
                if (key not in fired_propose and pr["t"] <= now
                        and now - getattr(self, "_last_propose_try",
                                          0) >= 1.0):
                    if self._wal_epoch() >= pr["epoch"]:
                        fired_propose.add(key)
                    else:
                        self.admin({"op": "propose", "epoch": pr["epoch"]})
                        self._last_propose_try = now
            self.run_timed()
            if now - last_motion >= 0.2:
                last_motion = now
                if self.sched.get("motion_source", "runner") == "runner":
                    self.motion_tick()
        # drain
        for _ in range(20):
            try:
                rclpy.spin_once(self.node, timeout_sec=0.1)
            except Exception:
                break
        metrics = self.compute_metrics()
        # T1.3a workload validity (automatic; INVALID_WORKLOAD records
        # are excluded from every liveness gate, no human judgment).
        import math as _math2
        gst = getattr(self, "_gst", None)
        fired = getattr(self, "_fired_fault_times", [])
        gst_json = (None if gst is None or gst == _math2.inf else gst)
        if not self.sched.get("faults"):
            workload_valid, workload_reason = True, "no-faults"
        elif gst is None or gst == _math2.inf:
            workload_valid, workload_reason = False, "no-finite-gst"
        elif any(t > gst for t in fired):
            workload_valid, workload_reason = False, "post-gst-fault"
        elif self.elapsed() < gst:
            workload_valid, workload_reason = False, "no-gst-reached"
        else:
            workload_valid, workload_reason = True, "gst-reached"
        record = {"schedule": self.sched, "domain": self.domain,
                  "events": self.events, "states": self.states,
                  "commits_seen": self.commits_seen,
                  "txn_events": self.txn_events,
                  "proposes_issued": getattr(self, "_seq_issued", None),
                  "gst": gst_json,
                  "workload_valid": workload_valid,
                  "workload_reason": workload_reason,
                  "truncated": truncated,
                  "runner_sha256": _sha_of_self(),
                  "metrics": metrics}
        self.out.write_text(json.dumps(record, indent=2, sort_keys=True)
                            + "\n")
        self.kill_all()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        print(json.dumps({"status": "run-done", "out": str(self.out),
                          "metrics": metrics}, sort_keys=True))

    def compute_metrics(self):
        evs = self.events
        auth = sorted(self.commits_seen)  # (t, epoch) authoritative
        maxep_at = {}
        cur = 0
        for t, e in auth:
            cur = max(cur, int(e))
            maxep_at[t] = cur

        def fleet_max(t):
            m = 0
            for tt, e in auth:
                if tt <= t:
                    m = max(m, int(e))
            return m

        def supersede_t(req):
            for tt, e in auth:
                if int(e) > req:
                    return tt
            return None

        stale, stale_durs = 0, []
        rejected = 0
        for e in evs:
            if e.get("verdict") == "EXECUTED":
                req = int(e.get("required_epoch", -1))
                # _rt and commits_seen share absolute time.monotonic base.
                t = float(e.get("_rt", 0))
                if req < fleet_max(t):
                    stale += 1
                    st = supersede_t(req)
                    if st is not None:
                        stale_durs.append(max(0.0, t - st))
            elif e.get("verdict") in ("REJECTED", "HELD"):
                rejected += 1
        # rollbacks / reconciliations from state snapshots
        rollbacks = 0
        last_com: dict[str, int] = {}
        reconciles = 0
        prev_rec: dict[str, bool] = {}
        for s in self.states:
            if s.get("role") != "agent":
                continue
            rid = s.get("id")
            c = int(s.get("committed", 0))
            if rid in last_com and c < last_com[rid]:
                rollbacks += 1
            last_com[rid] = c
            rec = bool(s.get("reconciled", True))
            if rid in prev_rec and (not prev_rec[rid]) and rec:
                reconciles += 1
            prev_rec[rid] = rec
        max_stale_ms = (max(stale_durs) * 1000.0) if stale_durs else 0.0
        return {
            "stale_motion_count": stale,
            "max_stale_motion_duration_ms": round(max_stale_ms, 1),
            "stale_commands_rejected": rejected,
            "epoch_rollback_count": rollbacks,
            "reconciliations": reconciles,
            "n_events": len(evs),
            "n_states": len(self.states),
            "n_commits_seen": len(auth),
        }


def rclpy_spin(node):
    try:
        import rclpy

        rclpy.spin_once(node, timeout_sec=0.05)
    except Exception:
        pass


def _sha_of_self() -> str:
    import hashlib

    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--domain-id", type=int, required=True)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--settle-s", type=float, default=3.0)
    ap.add_argument("--motion-source", default="runner",
                    choices=("runner", "external"),
                    help="witness mode: external waypoint drivers feed "
                    "motion_cmd; runner only faults/proposes/metrics")
    args = ap.parse_args()

    sched = json.loads(Path(args.schedule).read_text())
    sched["motion_source"] = args.motion_source
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(f"refusing to overwrite record: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    r = Runner(sched, out, args.domain_id, Path(args.repo), args.python,
               args.settle_s)
    r.run()


if __name__ == "__main__":
    main()
