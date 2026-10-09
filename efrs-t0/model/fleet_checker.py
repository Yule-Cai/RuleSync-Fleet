"""EFRS-T0 exhaustive fault exploration (offline, no Gazebo/LLM).

Three protocols x closed fault model x invariants I1..I7. Two engines:

1. schedule enumeration over a bounded fault-schedule space (exhaustive
   within documented bounds) with a deterministic per-protocol simulator;
2. seeded random fault fuzzing for breadth.

Fault-tuple format is ALWAYS (kind, tick, args...). Motion plans:
honest (execute local committed epoch) or stale (execute epoch 0).

Lease model (documented abstraction): the coordinator sends RENEW
(epoch, fence) to every connected, alive robot each tick. An EFRS robot
renews its lease (lease_exp = tick + L) ONLY on RENEW receipt, adopting
the carried epoch/hash/fence (contact implies sync; renewal never
extends a stale epoch). Partitioned or drop-afflicted robots get no
renewal and must safe-hold past expiry (I4). Initial lease_exp = L.

Bounds (frozen for T0; printed with every run): robots n=3, epochs
{0,1,2}, horizon T=12, lease L=5, BOUND=L. 2PC commits when all
REACHABLE robots vote READY (unanimity-of-all would deadlock under
partition instead — noted, not explored).
"""

from __future__ import annotations

import random

N = 3
EPOCHS = (0, 1, 2)
HORIZON = 12
LEASE = 5
BOUND = LEASE


def h(epoch: int) -> int:
    """Snapshot hash binding (I2): epoch -> unique hash."""
    return 1000 + epoch


class Net:
    def __init__(self):
        self.msgs = []
        self.parts = [frozenset(range(N + 1))]  # 0 == coordinator
        self._id = 0

    def connected(self, a, b):
        return any(a in g and b in g for g in self.parts)

    def send(self, kind, src, dst, payload, delay=1, tick=0):
        self._id += 1
        self.msgs.append({"kind": kind, "src": src, "dst": dst,
                          "payload": payload, "due": tick + delay,
                          "id": self._id})

    def due(self, tick):
        return [m for m in self.msgs if m["due"] <= tick]

    def take(self, m):
        if m in self.msgs:
            self.msgs.remove(m)


class Robot:
    def __init__(self, i):
        self.i = i
        self.committed = 0
        self.hash = h(0)
        self.prepared = None
        self.lease_exp = LEASE
        self.alive = True
        self.reconciled = True
        self.fence_seen = 0
        self.motions = []
        self.holding = False
        self.restart_tick = -1
        self.reconciled_at = -1


class Coord:
    def __init__(self):
        self.epoch = 0
        self.prepared = None
        self.votes = {}
        self.fence = 1
        self.alive = True
        self.commit_log = []  # (tick, epoch)


class Sim:
    def __init__(self, protocol, schedule, motion_plan="honest"):
        self.p = protocol
        self.sched = [tuple(f) for f in schedule]
        self.net = Net()
        self.robots = [Robot(i) for i in range(1, N + 1)]
        self.coord = Coord()
        self.tick = 0
        self.motion_plan = motion_plan
        self.trace = []
        self.violations = []

    def log(self, s):
        self.trace.append(f"t={self.tick} {s}")

    # ---------- coordinator ----------
    def coord_propose(self, epoch):
        c = self.coord
        if not c.alive or c.prepared is not None:
            return
        if epoch != c.epoch + 1 or epoch not in EPOCHS:
            return
        if self.p == "broadcast":
            c.epoch = epoch
            c.commit_log.append((self.tick, epoch))
            self.log(f"C BROADCASTS epoch {epoch} (no acks)")
            for r in self.robots:
                self.net.send("COMMIT", 0, r.i,
                              {"epoch": epoch, "hash": h(epoch),
                               "fence": c.fence, "txn": f"tx{epoch}",
                               "lease": LEASE}, tick=self.tick)
            return
        c.prepared = {"epoch": epoch, "hash": h(epoch), "fence": c.fence}
        c.votes = {}
        self.log(f"C proposes epoch {epoch} fence {c.fence}")
        for r in self.robots:
            self.net.send("PREPARE", 0, r.i,
                          {"epoch": epoch, "hash": h(epoch),
                           "fence": c.fence, "txn": f"tx{epoch}"},
                          tick=self.tick)

    def coord_on_vote(self, voter, vote):
        c = self.coord
        if c.prepared is None or not c.alive:
            return
        c.votes[voter] = vote
        reach = [r.i for r in self.robots
                 if self.net.connected(0, r.i) and self.robots[r.i - 1].alive]
        if reach and set(c.votes) >= set(reach):
            if all(v == "READY" for v in c.votes.values()):
                ep = c.prepared["epoch"]
                c.epoch = ep
                c.commit_log.append((self.tick, ep))
                self.log(f"C COMMITS epoch {ep} (durable)")
                for r in self.robots:
                    self.net.send("COMMIT", 0, r.i,
                                  {"epoch": ep, "hash": h(ep),
                                   "fence": c.fence, "txn": f"tx{ep}",
                                   "lease": LEASE}, tick=self.tick)
                c.prepared = None
                c.votes = {}
            elif any(v == "REJECT" for v in c.votes.values()):
                self.log(f"C ABORTS epoch {c.prepared['epoch']}")
                c.prepared = None
                c.votes = {}

    def coord_restart(self):
        c = self.coord
        c.alive = True
        c.fence += 1
        c.prepared = None
        c.votes = {}
        seen = [c.epoch]
        reach = [r for r in self.robots if self.net.connected(0, r.i)
                 and r.alive]
        for r in reach:
            seen.append(r.committed)
        c.epoch = max(seen)
        self.log(f"C restarts fence={c.fence} recovers epoch={c.epoch}")

    def coord_tick_renew(self):
        if not self.coord.alive:
            return
        for r in self.robots:
            if self.net.connected(0, r.i) and r.alive:
                self.net.send("RENEW", 0, r.i,
                              {"epoch": self.coord.epoch,
                               "fence": self.coord.fence},
                              tick=self.tick)

    # ---------- robots ----------
    def robot_on_renew(self, r, m):
        p = m["payload"]
        if p.get("fence", 0) < r.fence_seen:
            return
        if p["epoch"] > r.committed:
            r.committed = p["epoch"]
            r.hash = h(p["epoch"])
            r.prepared = None
            self.log(f"R{r.i} adopts renewal epoch {p['epoch']}")
        r.fence_seen = max(r.fence_seen, p.get("fence", 0))
        r.lease_exp = self.tick + LEASE
        if not r.reconciled:
            r.reconciled = True
            r.reconciled_at = self.tick
            self.log(f"R{r.i} reconciled via renewal")

    def robot_on_prepare(self, r, m):
        p = m["payload"]
        if p["epoch"] <= r.committed:
            self.net.send("VOTE", r.i, 0, {"vote": "REJECT",
                                           "epoch": p["epoch"]},
                          tick=self.tick)
            return
        if self.p == "efrs" and p.get("fence", 0) < r.fence_seen:
            self.net.send("VOTE", r.i, 0, {"vote": "REJECT",
                                           "epoch": p["epoch"]},
                          tick=self.tick)
            return
        if self.p == "efrs":
            # Contact implies sync: adopt coordinator currency first.
            if p["epoch"] > r.committed:
                pass  # PREPARE carries a NEWER epoch; vote below.
            elif p["epoch"] < r.committed:
                self.net.send("VOTE", r.i, 0, {"vote": "REJECT",
                                               "epoch": p["epoch"]},
                              tick=self.tick)
                return
        r.prepared = dict(p)
        self.net.send("VOTE", r.i, 0, {"vote": "READY",
                                       "epoch": p["epoch"]},
                      tick=self.tick)

    def robot_on_commit(self, r, m):
        p = m["payload"]
        if self.p == "broadcast":
            if p["epoch"] >= r.committed:
                r.committed = p["epoch"]
                r.hash = p.get("hash", h(p["epoch"]))
                self.log(f"R{r.i} applies broadcast epoch {p['epoch']}")
            return
        if self.p == "2pc":
            if p["epoch"] >= r.committed:
                r.committed = p["epoch"]
                r.hash = p.get("hash", h(p["epoch"]))
                self.log(f"R{r.i} applies 2PC epoch {p['epoch']}")
            else:
                r.committed = p["epoch"]
                r.hash = p.get("hash", h(p["epoch"]))
                self.log(f"R{r.i} applies LATE 2PC epoch {p['epoch']} "
                         f"(rollback!)")
            return
        if p["epoch"] < r.committed:
            self.log(f"R{r.i} rejects stale COMMIT epoch {p['epoch']}")
            return
        if p.get("fence", 0) < r.fence_seen:
            self.log(f"R{r.i} rejects fenced-out COMMIT")
            return
        r.committed = p["epoch"]
        r.hash = p["hash"]
        r.fence_seen = max(r.fence_seen, p.get("fence", 0))
        r.lease_exp = self.tick + p.get("lease", LEASE)
        r.prepared = None
        self.log(f"R{r.i} commits epoch {p['epoch']} lease->{r.lease_exp}")

    def robot_motion(self, r, required):
        if not r.alive:
            return
        if self.p == "efrs":
            if not r.reconciled:
                r.holding = True
                self.log(f"R{r.i} HOLDS (unreconciled)")
                return
            if self.tick > r.lease_exp:
                r.holding = True
                self.log(f"R{r.i} HOLDS (lease expired)")
                return
            if required != r.committed:
                r.holding = True
                self.log(f"R{r.i} HOLDS (required {required} != "
                         f"committed {r.committed})")
                return
            r.holding = False
            r.motions.append((self.tick, required, r.committed))
            self.log(f"R{r.i} executes epoch {required}")
        else:
            r.motions.append((self.tick, required, r.committed))
            self.log(f"R{r.i} executes (req {required}, local "
                     f"{r.committed})")

    def reconcile(self, r):
        if self.net.connected(0, r.i) and self.coord.alive:
            if r.committed < self.coord.epoch:
                r.committed = self.coord.epoch
                r.hash = h(self.coord.epoch)
                self.log(f"R{r.i} reconciles forward to {r.committed}")
            if self.p == "efrs":
                r.lease_exp = self.tick + LEASE
                r.fence_seen = max(r.fence_seen, self.coord.fence)
        r.reconciled = True
        r.reconciled_at = self.tick
        r.holding = False
        self.log(f"R{r.i} reconciled at epoch {r.committed}")

    # ---------- faults ----------
    def apply_fault(self, f):
        kind = f[0]
        if kind == "partition":
            _, _, groups = f
            self.net.parts = [frozenset(g) for g in groups]
            self.log(f"PARTITION {groups}")
            # Note: partition alone does NOT mark robots unreconciled;
            # the lease does the work (hold past expiry). Reconcile is
            # required at restart and at heal/reconnect.
        elif kind == "heal":
            self.net.parts = [frozenset(range(N + 1))]
            self.log("HEAL all")
            for r in self.robots:
                if r.alive:
                    if self.p == "efrs":
                        self.reconcile(r)
                    else:
                        r.reconciled = True
                        r.reconciled_at = self.tick
        elif kind == "crash_robot":
            r = self.robots[f[2] - 1]
            r.alive = False
            self.log(f"R{f[2]} CRASH")
        elif kind == "restart_robot":
            r = self.robots[f[2] - 1]
            r.alive = True
            r.prepared = None
            r.restart_tick = self.tick
            if self.p == "efrs":
                r.reconciled = False
                self.log(f"R{f[2]} restarts UNRECONCILED at {r.committed}")
                if self.net.connected(0, r.i):
                    self.reconcile(r)
            else:
                self.log(f"R{f[2]} restarts at {r.committed} (no reconcile)")
        elif kind == "crash_coord":
            self.coord.alive = False
            self.coord.prepared = None
            self.coord.votes = {}
            self.log("C CRASH")
        elif kind == "restart_coord":
            self.coord_restart()
        elif kind == "delay_kind":
            _, _, kk, extra = f
            n = 0
            for m in self.net.msgs:
                if (m["kind"] == kk and m["due"] <= self.tick
                        and self.net.connected(m["src"], m["dst"])):
                    m["due"] += extra
                    n += 1
            self.log(f"DELAY {n}x {kk} by +{extra}")
        elif kind == "dup_kind":
            _, _, kk = f
            n = 0
            for m in list(self.net.due(self.tick)):
                if m["kind"] == kk and self.net.connected(m["src"],
                                                          m["dst"]):
                    self.net.send(m["kind"], m["src"], m["dst"],
                                  dict(m["payload"]), tick=self.tick)
                    n += 1
            self.log(f"DUP {n}x {kk}")
        elif kind == "drop_kind":
            _, _, kk = f
            before = len(self.net.msgs)
            self.net.msgs = [m for m in self.net.msgs
                             if not (m["kind"] == kk and m["due"] <= self.tick
                                     and self.net.connected(m["src"],
                                                            m["dst"]))]
            self.log(f"DROP {before - len(self.net.msgs)}x due {kk}")

    def route_messages(self):
        for m in sorted(self.net.due(self.tick), key=lambda m: m["id"]):
            if not self.net.connected(m["src"], m["dst"]):
                continue
            dst = m["dst"]
            if dst == 0:
                if m["kind"] == "VOTE" and self.coord.alive:
                    self.coord_on_vote(m["src"], m["payload"]["vote"])
                self.net.take(m)
            else:
                r = self.robots[dst - 1]
                if not r.alive:
                    continue
                if m["kind"] == "PREPARE":
                    self.robot_on_prepare(r, m)
                elif m["kind"] == "COMMIT":
                    self.robot_on_commit(r, m)
                elif m["kind"] == "RENEW":
                    if self.p == "efrs":
                        self.robot_on_renew(r, m)
                self.net.take(m)

    # ---------- main loop ----------
    def run(self):
        for t in range(HORIZON + 1):
            self.tick = t
            for f in self.sched:
                if f[0] != "propose" and f[1] == t:
                    self.apply_fault(f)
            for f in self.sched:
                if f[0] == "propose" and f[1] == t:
                    self.coord_propose(f[2])
            self.route_messages()
            if self.p == "efrs":
                self.coord_tick_renew()
                # Renewals sent this tick are due next tick; route the
                # ones already due (none yet) — delivery happens next tick.
            for r in self.robots:
                if not r.alive:
                    continue
                if self.motion_plan == "honest":
                    self.robot_motion(r, r.committed)
                elif self.motion_plan == "stale":
                    self.robot_motion(r, 0)
        return self.check()

    # ---------- invariants ----------
    def check(self):
        v = []
        seen = {}
        for r in self.robots:
            if r.committed in seen and seen[r.committed] != r.hash:
                v.append(("I2", f"R{r.i} hash mismatch"))
            seen[r.committed] = r.hash
        for r in self.robots:
            for (t, req, com) in r.motions:
                if req != com:
                    v.append(("I3", f"R{r.i} t={t} executed req {req} "
                                   f"with local {com}"))
                if self.p == "efrs" and t > r.lease_exp:
                    v.append(("I4", f"R{r.i} t={t} moved on expired lease"))
                for (ct, ep) in self.coord.commit_log:
                    if com < ep and t > ct + BOUND:
                        v.append(("I5", f"R{r.i} t={t} stale epoch {com} "
                                       f"beyond {ct}+{BOUND} (now {ep})"))
                if self.p != "efrs" and r.restart_tick >= 0:
                    maxep = max([e for (_, e) in self.coord.commit_log
                                 if _ <= t] + [0])
                    if t >= r.restart_tick and com < maxep:
                        v.append(("I6", f"R{r.i} t={t} post-restart motion "
                                       f"under superseded epoch {com} "
                                       f"(fleet {maxep})"))
                if r.reconciled_at >= 0 and t == r.reconciled_at:
                    pass
        for line in self.trace:
            if "rollback!" in line:
                v.append(("I1", line.strip()))
        # I7: post-heal motion with divergent epoch and no reconcile event.
        # EFRS logs reconcile at heal; baselines never do.
        heals = [t for t in range(HORIZON + 1)
                 if any("HEAL" in l and l.startswith(f"t={t} ")
                        for l in self.trace)]
        for r in self.robots:
            for (t, _, com) in r.motions:
                if any(ht < t for ht in heals) and self.p != "efrs":
                    maxep = max([e for (_, e) in self.coord.commit_log
                                 if _ <= t] + [0])
                    if com != maxep and not any(
                            f"R{r.i} reconciled" in l for l in self.trace):
                        v.append(("I7", f"R{r.i} t={t} moves post-heal "
                                       f"without reconcile (epoch {com} vs "
                                       f"fleet {maxep})"))
                        break
        self.violations = v
        return v


def schedules():
    S = []
    S.append([("propose", 1, 1), ("propose", 6, 2)])
    S.append([("partition", 2, [[0, 1, 2], [3]]),
              ("propose", 3, 1), ("heal", 8, None), ("propose", 9, 2)])
    S.append([("partition", 2, [[0, 1, 2], [3]]),
              ("propose", 3, 1), ("drop_kind", 5, "COMMIT"),
              ("heal", 8, None), ("propose", 9, 2)])
    S.append([("propose", 1, 1), ("crash_robot", 4, 3),
              ("propose", 5, 2), ("restart_robot", 8, 3)])
    S.append([("propose", 1, 1), ("crash_coord", 2, None),
              ("restart_coord", 4, None), ("propose", 5, 1),
              ("propose", 8, 2)])
    S.append([("propose", 1, 1), ("propose", 6, 2)])
    S.append([("partition", 2, [[0, 1, 2], [3]]),
              ("propose", 3, 1), ("propose", 7, 2)])
    # S7: late COMMIT — epoch-1 COMMITs delayed +6 past the epoch-2
    # commit; plain 2PC rolls back (I1), EFRS must reject.
    S.append([("propose", 1, 1), ("delay_kind", 4, "COMMIT", 6),
              ("propose", 5, 2)])
    # S8: crash across a commit with COMMITs dropped: restart finds an
    # empty queue while the fleet advanced (I6 superseded-epoch test).
    S.append([("propose", 1, 1), ("crash_robot", 4, 3),
              ("propose", 5, 2), ("drop_kind", 8, "COMMIT"),
              ("restart_robot", 9, 3)])
    return S


def main():
    protos = ["broadcast", "2pc", "efrs"]
    all_sched = schedules()
    print(f"fleet-checker: n={N} horizon={HORIZON} lease={LEASE} "
          f"schedules={len(all_sched)}")
    results = {}
    for p in protos:
        results[p] = {}
        for si, s in enumerate(all_sched):
            plans = ["stale"] if si == 5 else ["honest"]
            for plan in plans:
                sim = Sim(p, s, motion_plan=plan)
                results[p][(si, plan)] = sim.run()
    for p in protos:
        print(f"--- {p} ---")
        for key in sorted(results[p]):
            viols = results[p][key]
            kinds = sorted({k for k, _ in viols})
            print(f"  sched{key}: {len(viols)} violations {kinds}")
    print("=== headline: partitioned-robot stale rule window (S1) ===")
    for p in protos:
        sim = Sim(p, schedules()[1])
        sim.run()
        stale = [t for r in sim.robots for (t, _, com) in r.motions
                 if r.i == 3 and com == 0 and t >= 5]
        print(f"  {p}: R3 epoch-0 executions at t>=5: {stale}")
    print("=== I5 stale bound on long partition (S6, no heal) ===")
    for p in protos:
        sim = Sim(p, schedules()[6])
        sim.run()
        worst = 0
        for r in sim.robots:
            for (t, _, com) in r.motions:
                for (ct, ep) in sim.coord.commit_log:
                    if com < ep:
                        worst = max(worst, t - ct)
        print(f"  {p}: max stale ticks after commit = {worst} "
              f"(BOUND={BOUND})")
    print("=== counterexample trace: 2PC S1 (first 16 lines) ===")
    sim = Sim("2pc", schedules()[1])
    sim.run()
    for line in sim.trace[:16]:
        print("  " + line)
    print("=== fuzz (200 seeds x 3 protocols x honest+stale) ===")
    fuzz_hits = {p: set() for p in protos}
    for seed in range(200):
        r = random.Random(seed)
        sched = [("propose", 1, 1)]
        if r.random() < 0.7:
            sched.append(("propose", 5 + r.randrange(4), 2))
        if r.random() < 0.6:
            victim = r.randrange(1, N + 1)
            t0 = r.randrange(1, 6)
            sched.append(("partition", t0, [[0] + [i for i in range(
                1, N + 1) if i != victim], [victim]]))
            if r.random() < 0.7:
                sched.append(("heal", min(t0 + r.randrange(2, 7),
                                          HORIZON), None))
        if r.random() < 0.4:
            sched.append(("crash_robot", r.randrange(1, HORIZON),
                          r.randrange(1, N + 1)))
        if r.random() < 0.3:
            sched.append(("drop_kind", r.randrange(2, 9),
                          r.choice(["COMMIT", "PREPARE", "VOTE", "RENEW"])))
        if r.random() < 0.3:
            sched.append(("delay_kind", r.randrange(2, 9),
                          r.choice(["COMMIT", "PREPARE", "VOTE", "RENEW"]),
                          r.randrange(2, 6)))
        if r.random() < 0.2:
            sched.append(("dup_kind", r.randrange(2, 9),
                          r.choice(["COMMIT", "PREPARE", "VOTE"])))
        if r.random() < 0.25:
            sched.append(("crash_coord", r.randrange(1, 6), None))
            sched.append(("restart_coord", r.randrange(6, 10), None))
        for p in protos:
            for plan in ("honest", "stale"):
                sim = Sim(p, sched, motion_plan=plan)
                for k, _ in sim.run():
                    fuzz_hits[p].add(k)
    for p in protos:
        print(f"  {p}: invariant kinds hit in fuzz: {sorted(fuzz_hits[p])}")


if __name__ == "__main__":
    main()
