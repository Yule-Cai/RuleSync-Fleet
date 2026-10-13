"""EFRS-T1.2 exhaustive fault exploration (offline, no Gazebo/LLM).

Extends the T1.1 model with the T1.2 congestion-safe recovery shape,
per docs/EFRS_T12_PREREGISTRATION.md §§D–G (frozen BEFORE results):

- ONE PREPARE per attempt (no in-attempt retransmission); recovery by
  new-generation retry only (bounded rate).
- ONE VOTE per robot per txn_id (duplicates recognized, never re-sent);
  ONE COMMIT per durable decision (+ one restart replay); ONE ACK per
  robot per txn (evidence only, never redriven).
- Missed-COMMIT catch-up ONLY through reconcile-pull on newer-epoch
  contact (existing T1.1 pull path); lease expiry HOLDs while
  disconnected.
- Contact-sync tightening, txn identity, timeout ABORT, restart
  disambiguation: unchanged from T1.1.
- Liveness monitor fires ONLY on EVENTUAL_HEAL schedules; permanent-
  loss schedules assert safety/HOLD only (never commit expectation).

Bounds: n=3, epochs {0,1,2}, horizon 12, lease 5, BOUND=5,
VOTE_WINDOW_TICKS=3, RETRY_DELAY_TICKS=1 (all inherited).
Safety semantics (I1..I7, thresholds) unchanged.
"""

from __future__ import annotations

import random

N = 3
EPOCHS = (0, 1, 2)
HORIZON = 12
LEASE = 5
BOUND = LEASE
# T1.1 frozen attempt timing (model ticks; see prereg §2 for the map to
# the frozen 1500 ms ROS deadline and 100 ms heartbeat period).
VOTE_WINDOW_TICKS = 3
RETRY_DELAY_TICKS = 1


def h(epoch: int) -> int:
    """Snapshot hash binding (I2): epoch -> unique hash."""
    return 1000 + epoch


def txn(epoch: int, gen: int):
    """Transaction attempt identity: (candidate_epoch, hash, generation)."""
    return (epoch, h(epoch), gen)


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
        self.prepared = None  # T1.1: full txn payload incl. gen
        self.voted_txn = None  # T1.1: last txn voted (duplicate recognition)
        self.acked_txn = set()  # T1.2 §D4: txns already ACKed (at most one)
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
        self.prepared = None  # T1.1: {epoch,hash,fence,txn,gen}
        self.votes = {}
        self.deadline = -1  # T1.1: attempt deadline tick
        self.gen = {}  # T1.1: epoch -> last attempt generation used
        self.aborted = set()  # T1.1: terminal (epoch, gen) attempts
        self.rejected_terminal = set()  # T1.1: epochs reject-aborted
        self.pending = None  # T1.1: requested-but-uncommitted epoch
        self.reattempt_at = -1  # T1.1: earliest tick for next attempt
        self.acked = {}  # T1.1: committed epoch -> set of robots acked
        self.fence = 1
        self.alive = True
        self.commit_log = []  # (tick, epoch)
        self.abort_log = []  # T1.1: (tick, epoch, gen)
        self.seen_proposes = []  # T1.1: epochs ever proposed (restart)
        self.ignored_late = 0  # T1.1: late/superseded msgs ignored


class Sim:
    def __init__(self, protocol, schedule, motion_plan="honest",
                 horizon=HORIZON):
        self.p = protocol
        self.sched = [tuple(f) for f in schedule]
        self.horizon = horizon
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
    # ---------- coordinator (T1.1 transaction layer) ----------
    def coord_propose(self, epoch):
        c = self.coord
        if not c.alive:
            return
        if epoch != c.epoch + 1 or epoch not in EPOCHS:
            return
        c.seen_proposes.append(epoch)
        if self.p == "broadcast":
            c.epoch = epoch
            c.commit_log.append((self.tick, epoch))
            self.log(f"C BROADCASTS epoch {epoch} (no acks)")
            for r in self.robots:
                self.net.send("COMMIT", 0, r.i,
                              {"epoch": epoch, "hash": h(epoch),
                               "fence": c.fence, "txn": txn(epoch, 0),
                               "lease": LEASE}, tick=self.tick)
            return
        if c.prepared is not None:
            return  # one active attempt per epoch; never overlap
        if self.p == "efrs":
            # Re-propose of the same pending epoch starts a fresh
            # generation (never resurrects an aborted gen). A
            # reject-aborted epoch is terminal: only a NEW epoch may
            # proceed.
            if epoch in c.rejected_terminal:
                self.log(f"C ignores re-propose of reject-aborted "
                         f"epoch {epoch}")
                return
            g = c.gen.get(epoch, -1) + 1
            if (epoch, g) in c.aborted:
                g += 1
            c.gen[epoch] = g
            c.pending = epoch
            self.coord_begin_attempt(epoch, g)
            return
        # baselines: single-shot attempt, T0 behavior preserved
        c.prepared = {"epoch": epoch, "hash": h(epoch), "fence": c.fence,
                      "txn": txn(epoch, 0), "gen": 0}
        c.votes = {}
        self.log(f"C proposes epoch {epoch} fence {c.fence}")
        for r in self.robots:
            self.net.send("PREPARE", 0, r.i,
                          {"epoch": epoch, "hash": h(epoch),
                           "fence": c.fence, "txn": txn(epoch, 0)},
                          tick=self.tick)

    def coord_begin_attempt(self, epoch, gen):
        c = self.coord
        t = txn(epoch, gen)
        c.prepared = {"epoch": epoch, "hash": h(epoch), "fence": c.fence,
                      "txn": t, "gen": gen}
        c.votes = {}
        c.deadline = self.tick + VOTE_WINDOW_TICKS
        c.reattempt_at = -1
        self.log(f"C proposes epoch {epoch} gen {gen} fence {c.fence}")
        for r in self.robots:
            self.net.send("PREPARE", 0, r.i,
                          {"epoch": epoch, "hash": h(epoch),
                           "fence": c.fence, "txn": t}, tick=self.tick)

    def coord_retransmit_prepare(self):
        """T1.2 §D1: REMOVED (no in-attempt retransmission).

        Kept as an explicit no-op so call sites document the former
        behavior; recovery runs through new generations only.
        Source-contract tested at the ROS layer (§P).
        """
        return

    def coord_timeout_abort(self):
        """Explicit abort at the deadline; MUST leave the round."""
        c = self.coord
        if self.p != "efrs" or c.prepared is None or not c.alive:
            return
        if self.tick < c.deadline:
            return
        p = c.prepared
        c.aborted.add((p["epoch"], p["gen"]))
        c.abort_log.append((self.tick, p["epoch"], p["gen"]))
        self.log(f"C TIMEOUT-ABORTS txn {p['txn']}")
        for r in self.robots:
            self.net.send("ABORT", 0, r.i,
                          {"epoch": p["epoch"], "txn": p["txn"],
                           "gen": p["gen"]}, tick=self.tick)
        c.prepared = None
        c.votes = {}
        c.reattempt_at = self.tick + RETRY_DELAY_TICKS

    def coord_auto_reattempt(self):
        c = self.coord
        if self.p != "efrs" or not c.alive:
            return
        if c.prepared is not None or c.pending is None:
            return
        if c.pending != c.epoch + 1 or c.pending not in EPOCHS:
            c.pending = None
            return
        if self.tick < c.reattempt_at:
            return
        g = c.gen.get(c.pending, -1) + 1
        if (c.pending, g) in c.aborted:
            g += 1
        c.gen[c.pending] = g
        self.log(f"C auto-reattempts epoch {c.pending} gen {g}")
        self.coord_begin_attempt(c.pending, g)

    def coord_retransmit_commit(self):
        """T1.2 §D3: REMOVED (no ACK-driven redrive).

        Catch-up runs through reconcile-pull on newer-epoch contact
        (robot_on_renew pull path) only. Kept as an explicit no-op.
        """
        return

    def coord_on_vote(self, voter, vote, t=None):
        c = self.coord
        if c.prepared is None or not c.alive:
            c.ignored_late += 1
            return
        if self.p == "efrs":
            if t != c.prepared["txn"]:
                # Late vote from a terminal/superseded attempt: ignore.
                c.ignored_late += 1
                self.log(f"C ignores late vote from {voter} txn {t}")
                return
        c.votes[voter] = vote
        reach = [r.i for r in self.robots
                 if self.net.connected(0, r.i) and self.robots[r.i - 1].alive]
        if reach and set(c.votes) >= set(reach):
            if all(v == "READY" for v in c.votes.values()):
                ep = c.prepared["epoch"]
                c.epoch = ep
                c.commit_log.append((self.tick, ep))
                if self.p == "efrs":
                    c.acked[ep] = set()
                    c.pending = None
                self.log(f"C COMMITS epoch {ep} (durable)")
                for r in self.robots:
                    self.net.send("COMMIT", 0, r.i,
                                  {"epoch": ep, "hash": h(ep),
                                   "fence": c.fence,
                                   "txn": c.prepared["txn"],
                                   "lease": LEASE}, tick=self.tick)
                c.prepared = None
                c.votes = {}
            elif any(v == "REJECT" for v in c.votes.values()):
                if self.p == "efrs":
                    p = c.prepared
                    # Reject-abort is TERMINAL for the logical update
                    # (a hash/fence rejection would re-reject identically);
                    # only timeout-abort auto-reattempts.
                    c.aborted.add((p["epoch"], p["gen"]))
                    c.abort_log.append((self.tick, p["epoch"], p["gen"]))
                    c.rejected_terminal.add(p["epoch"])
                    c.pending = None
                    self.log(f"C REJECT-ABORTS txn {p['txn']} (terminal)")
                    for r in self.robots:
                        self.net.send("ABORT", 0, r.i,
                                      {"epoch": p["epoch"], "txn": p["txn"],
                                       "gen": p["gen"]}, tick=self.tick)
                    c.prepared = None
                    c.votes = {}
                else:
                    self.log(f"C ABORTS epoch {c.prepared['epoch']}")
                    c.prepared = None
                    c.votes = {}

    def coord_on_ack(self, robot, t):
        c = self.coord
        if self.p != "efrs" or not c.alive:
            return
        ep = t[0]
        c.acked.setdefault(ep, set()).add(robot)

    def coord_restart(self):
        c = self.coord
        c.alive = True
        c.fence += 1
        c.prepared = None
        c.votes = {}
        c.deadline = -1
        c.reattempt_at = -1
        seen = [c.epoch]
        reach = [r for r in self.robots if self.net.connected(0, r.i)
                 and r.alive]
        for r in reach:
            seen.append(r.committed)
        c.epoch = max(seen)
        # Durable decisions disambiguated from the logs: COMMITTED
        # epochs resume dissemination; ABORTED gens never resurrect
        # (gen counters + aborted set rebuilt from the logs).
        for (_, ep) in c.commit_log:
            c.acked.setdefault(ep, set())
        # Rebuild the pending logical update from durable history: the
        # smallest proposed-but-uncommitted epoch resumes (at a fresh
        # generation via the normal re-propose path, never resurrecting
        # an aborted gen).
        uncommitted = [e for e in c.seen_proposes
                       if e not in [ce for (_, ce) in c.commit_log]
                       and e == c.epoch + 1 and e in EPOCHS
                       and e not in c.rejected_terminal]
        c.pending = min(uncommitted) if uncommitted else None
        if c.pending is not None:
            c.reattempt_at = self.tick
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
        if self.p == "efrs":
            # T1.1 contact-sync (§J): RENEW never adopts. A renew for a
            # NEWER epoch triggers a reconcile-pull of the authoritative
            # committed epoch instead; adopted currency extends the
            # lease; obsolete currency is ignored entirely.
            if p["epoch"] > r.committed:
                if self.net.connected(0, r.i) and self.coord.alive \
                        and self.coord.epoch > r.committed:
                    r.committed = self.coord.epoch
                    r.hash = h(self.coord.epoch)
                    r.prepared = None
                    r.fence_seen = max(r.fence_seen, self.coord.fence)
                    r.lease_exp = self.tick + LEASE
                    r.reconciled = True
                    r.reconciled_at = self.tick
                    self.log(f"R{r.i} pulls authoritative epoch "
                             f"{r.committed} on newer renew")
                else:
                    self.log(f"R{r.i} ignores newer-epoch renew "
                             f"{p['epoch']} (authoritative unavailable)")
                return
            if p["epoch"] == r.committed:
                r.fence_seen = max(r.fence_seen, p.get("fence", 0))
                r.lease_exp = self.tick + LEASE
                if not r.reconciled:
                    r.reconciled = True
                    r.reconciled_at = self.tick
                    self.log(f"R{r.i} reconciled via renewal")
            else:
                self.log(f"R{r.i} ignores obsolete renew epoch "
                         f"{p['epoch']} (committed {r.committed})")
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
                                           "epoch": p["epoch"],
                                           "txn": p.get("txn")},
                          tick=self.tick)
            return
        if self.p == "efrs" and p.get("fence", 0) < r.fence_seen:
            self.net.send("VOTE", r.i, 0, {"vote": "REJECT",
                                           "epoch": p["epoch"],
                                           "txn": p.get("txn")},
                          tick=self.tick)
            return
        if self.p == "efrs":
            # Contact implies sync: adopt coordinator currency first.
            if p["epoch"] > r.committed:
                pass  # PREPARE carries a NEWER epoch; vote below.
            elif p["epoch"] < r.committed:
                self.net.send("VOTE", r.i, 0, {"vote": "REJECT",
                                               "epoch": p["epoch"],
                                               "txn": p.get("txn")},
                              tick=self.tick)
                return
            t = p.get("txn")
            if r.prepared is not None and r.prepared.get("txn") == t:
                # T1.2 §D2: duplicate PREPARE(identical txn) recognized;
                # at most ONE VOTE per robot per txn (no re-send).
                self.log(f"R{r.i} duplicate PREPARE txn {t} recognized")
                return
            if r.prepared is not None and r.prepared.get("txn") != t:
                self.log(f"R{r.i} supersedes {r.prepared.get('txn')} "
                         f"with txn {t}")
            r.prepared = dict(p)
            r.voted_txn = t
            self.net.send("VOTE", r.i, 0, {"vote": "READY",
                                           "epoch": p["epoch"],
                                           "txn": t}, tick=self.tick)
            return
        r.prepared = dict(p)
        self.net.send("VOTE", r.i, 0, {"vote": "READY",
                                       "epoch": p["epoch"]},
                      tick=self.tick)

    def robot_on_abort(self, r, m):
        p = m["payload"]
        if self.p != "efrs":
            return
        t = p.get("txn")
        if r.prepared is not None and r.prepared.get("txn") == t:
            r.prepared = None
            self.log(f"R{r.i} clears prepared on ABORT txn {t}")
        else:
            self.log(f"R{r.i} ignores ABORT txn {t} (no matching "
                     f"prepared)")
        # ABORT never touches committed state (asserted by I1).

    def robot_send_ack(self, r, t, ep):
        if self.p == "efrs" and t not in r.acked_txn:
            r.acked_txn.add(t)
            self.net.send("ACK", r.i, 0, {"txn": t, "epoch": ep},
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
        if self.p == "efrs":
            t = p.get("txn")
            if p["epoch"] == r.committed and p.get("hash") == r.hash:
                # Same decision, any generation: idempotent no-op
                # (never a rollback), still ACK.
                self.log(f"R{r.i} idempotent COMMIT txn {t}")
                self.robot_send_ack(r, t, p["epoch"])
                return
        r.committed = p["epoch"]
        r.hash = p["hash"]
        r.fence_seen = max(r.fence_seen, p.get("fence", 0))
        r.lease_exp = self.tick + p.get("lease", LEASE)
        r.prepared = None
        self.log(f"R{r.i} commits epoch {p['epoch']} lease->{r.lease_exp}")
        if self.p == "efrs":
            self.robot_send_ack(r, p.get("txn"), p["epoch"])

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
        elif kind == "inject_renew":
            # §J regression probe: forged RENEW delivered straight to a
            # robot, bypassing the coordinator (models a mutated or
            # replayed renewal). Payload: (robot, epoch).
            _, _, who, ep = f
            r = self.robots[who - 1]
            if r.alive:
                self.robot_on_renew(
                    r, {"payload": {"epoch": ep, "hash": h(ep)
                                    if ep in EPOCHS else 0,
                                    "fence": self.coord.fence}})
                self.log(f"INJECT forged RENEW epoch {ep} -> R{who}")

    def route_messages(self):
        for m in sorted(self.net.due(self.tick), key=lambda m: m["id"]):
            if not self.net.connected(m["src"], m["dst"]):
                continue
            dst = m["dst"]
            if dst == 0:
                if m["kind"] == "VOTE" and self.coord.alive:
                    self.coord_on_vote(m["src"], m["payload"]["vote"],
                                       m["payload"].get("txn"))
                elif m["kind"] == "ACK" and self.coord.alive:
                    self.coord_on_ack(m["src"], m["payload"].get("txn"))
                self.net.take(m)
            else:
                r = self.robots[dst - 1]
                if not r.alive:
                    continue
                if m["kind"] == "PREPARE":
                    self.robot_on_prepare(r, m)
                elif m["kind"] == "COMMIT":
                    self.robot_on_commit(r, m)
                elif m["kind"] == "ABORT":
                    self.robot_on_abort(r, m)
                elif m["kind"] == "RENEW":
                    if self.p == "efrs":
                        self.robot_on_renew(r, m)
                self.net.take(m)

    # ---------- main loop ----------
    def run(self, live_expected=None, converge=False):
        for t in range(self.horizon + 1):
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
                # T1.1 attempt pipeline (frozen timing, §2): republish
                # PREPARE to missing voters, abort at the deadline (MUST
                # leave the round), auto re-attempt one tick later,
                # redrive COMMIT to non-acked.
                self.coord_retransmit_prepare()
                self.coord_timeout_abort()
                self.coord_auto_reattempt()
                self.coord_retransmit_commit()
                # Renewals sent this tick are due next tick; route the
                # ones already due (none yet) — delivery happens next tick.
            for r in self.robots:
                if not r.alive:
                    continue
                if self.motion_plan == "honest":
                    self.robot_motion(r, r.committed)
                elif self.motion_plan == "stale":
                    self.robot_motion(r, 0)
        v = self.check()
        if live_expected:
            v = v + self.check_liveness(live_expected, converge)
        return v

    def check_liveness(self, expected_epochs, converge=False):
        """EVENTUAL_HEAL monitor: every expected logical epoch commits.

        converge (heal schedules only): every alive robot connected at
        the final tick has adopted the max committed epoch (catch-up via
        COMMIT delivery or reconcile-pull — never phantom adoption).
        """
        v = []
        committed = {ep for (_, ep) in self.coord.commit_log}
        for ep in expected_epochs:
            if ep not in committed:
                v.append(("LIVE", f"epoch {ep} never committed "
                                  f"(log {[e for (_, e) in self.coord.commit_log]})"))
        if converge and committed:
            top = max(committed)
            for r in self.robots:
                if r.alive and self.net.connected(0, r.i) \
                        and r.committed != top:
                    v.append(("LIVE", f"R{r.i} unconverged "
                                      f"({r.committed} vs fleet {top})"))
        return v

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


def schedules_t11():
    """T1.1 transaction-layer schedules: (schedule, live_expected).

    live_expected lists epochs that MUST commit by HORIZON (EVENTUAL_HEAL
    monitor). All fit HORIZON=12: abort ~3 ticks after propose,
    re-attempt 1 tick after abort, commit ~2 ticks after heal.
    """
    K = []
    # K1: first PREPARE batch dropped; retransmit recovers, no heal needed.
    K.append(([("propose", 1, 1), ("drop_kind", 2, "PREPARE")], [1]))
    # K2: first VOTE batch dropped; re-votes on retransmit recover.
    K.append(([("propose", 1, 1), ("drop_kind", 3, "VOTE")], [1]))
    # K3: two consecutive VOTE batches dropped.
    K.append(([("propose", 1, 1), ("drop_kind", 3, "VOTE"),
               ("drop_kind", 4, "VOTE")], [1]))
    # K4: TOTAL isolation across the first attempt (no reachable subset
    # to commit among); heal after first abort. Abort MUST fire, then
    # the re-attempt commits post-heal.
    K.append(([("partition", 1, [[0], [1], [2], [3]]), ("propose", 1, 1),
               ("heal", 6, None)], [1]))
    # K5: total isolation across TWO aborts; heal after the second.
    K.append(([("partition", 1, [[0], [1], [2], [3]]), ("propose", 1, 1),
               ("heal", 9, None)], [1]))
    # K6: partitioned robot's stale PREPARE/vote arrive post-heal for the
    # aborted gen (queued in flight); must be ignored, gen1 commits.
    K.append(([("partition", 1, [[0, 1, 2], [3]]), ("propose", 1, 1),
               ("heal", 7, None)], [1]))
    # K6b: explicit late vote (delayed past the abort, connected).
    K.append(([("propose", 1, 1), ("delay_kind", 2, "VOTE", 6)], [1]))
    # K7: late COMMIT from a superseded attempt past a newer commit
    # (generation-qualified S7); EFRS must not roll back.
    K.append(([("propose", 1, 1), ("delay_kind", 3, "COMMIT", 6),
               ("propose", 5, 2)], [1, 2]))
    # K8: coordinator restart between attempts; pending resumes fresh gen.
    K.append(([("propose", 1, 1), ("crash_coord", 2, None),
               ("restart_coord", 4, None)], [1]))
    # K9: restart after a durable COMMIT; dissemination resumes, nothing
    # resurrected, idempotent re-application only.
    K.append(([("propose", 1, 1), ("crash_coord", 5, None),
               ("restart_coord", 7, None)], [1]))
    # K10: duplicate PREPARE + duplicate COMMIT; exactly one decision.
    K.append(([("propose", 1, 1), ("dup_kind", 2, "PREPARE"),
               ("dup_kind", 5, "COMMIT")], [1]))
    return K


def schedules_t12():
    """T1.2 systematic set: (name, schedule, live_expected, converge,
    horizon). T1.1 K1-K10 kept (same faults, new mechanics); §G adds
    the rest. HORIZON=12 throughout except K12 (documented extension to
    16 for three abort cycles; lead authorization does not freeze model
    horizon). Every heal schedule heals ≥2 ticks before its horizon so
    catch-up can land (construction discipline).
    """
    L = []
    base = [(s, live) for (s, live) in schedules_t11()]
    names11 = ["K1-prepare-drop", "K2-vote-drop", "K3-votes-drop",
               "K4-heal-after-abort", "K5-heal-after-2aborts",
               "K6-stale-flight-postheal", "K6b-late-vote",
               "K7-late-commit-superseded", "K8-restart-between",
               "K9-restart-after-commit", "K10-duplicates"]
    for n, (s, live) in zip(names11, base):
        L.append((n, s, live, True, 12))
    # G-a: first COMMIT lost to all -> catch-up via renew-pull only
    # (no redrive exists anymore). Converge required.
    L.append(("G-a-commit-lost-pull-catchup",
              [("propose", 1, 1), ("drop_kind", 4, "COMMIT")], [1],
              True, 12))
    # G-b: one robot partitioned across the commit, heals right after;
    # late COMMIT + pull converge it.
    L.append(("G-b-one-missed-commit-heals",
              [("propose", 1, 1),
               ("partition", 3, [[0, 1, 2], [3]]),
               ("heal", 5, None)], [1], True, 12))
    # G-c: robot misses COMMIT then partitions until lease expiry:
    # safety/HOLD only, NO commit expectation for R3 (stays epoch 0,
    # holds, never phantom-adopts). live=[1] binds the FLEET decision;
    # convergence asserted only for connected robots (R3 excluded).
    L.append(("G-c-miss-then-dark-holds",
              [("propose", 1, 1), ("drop_kind", 4, "COMMIT"),
               ("partition", 4, [[0, 1, 2], [3]])], [1], True, 12))
    # G-d: permanent loss (no heal ever): safety/HOLD only, no liveness.
    L.append(("G-d-permanent-loss-holds",
              [("propose", 1, 1),
               ("drop_kind", 2, "PREPARE"),
               ("drop_kind", 3, "VOTE")], None, False, 12))
    # G-e: duplicate VOTE (one-vote rule: no re-send, single decision).
    L.append(("G-e-dup-vote",
              [("propose", 1, 1), ("dup_kind", 3, "VOTE")], [1],
              True, 12))
    # G-f: heal after 3 aborted generations (extended horizon, noted).
    L.append(("G-f-heal-after-3aborts",
              [("partition", 1, [[0], [1], [2], [3]]),
               ("propose", 1, 1), ("heal", 13, None)], [1],
              True, 16))
    return L


def regression_miss_commit_hold():
    """G-c exact assertions: dark robot holds, learns nothing, safe."""
    s = Sim("efrs", [("propose", 1, 1), ("drop_kind", 4, "COMMIT"),
                     ("partition", 4, [[0, 1, 2], [3]])],
            motion_plan="honest")
    v = s.run(live_expected=[1], converge=True)
    r3 = s.robots[2]
    late_motions = [t for (t, _, _) in r3.motions if t > 4 + LEASE + 1]
    holds = any("HOLDS (lease expired)" in l and "R3" in l
                for l in s.trace)
    ok = (not v and r3.committed == 0 and not late_motions and holds)
    return [("G-c dark robot holds without learning", ok,
             f"committed={r3.committed} late_motions={late_motions} "
             f"holds_logged={holds}")]


def regression_contact_sync():
    """§J micro-tests: forged currency never installs, never extends.

    Each scenario leaves no legitimate path to the forged epoch, so the
    end-state assertions are exact (not statistical).
    """
    out = []

    def fresh(proto="efrs"):
        return Sim(proto, [], motion_plan="honest")

    # J1: forged renew for a prepared-but-uncommitted epoch, coordinator
    # alive but epoch uncommitted: no adopt, no lease extension beyond
    # legitimate epoch-0 renews. (No propose at all: commit stays 0.)
    s = fresh()
    s.sched = [("inject_renew", 2, 1, 1)]
    s.run()
    r1 = s.robots[0]
    ok = (r1.committed == 0
          and not any("adopts renewal epoch 1" in l for l in s.trace)
          and not any("pulls authoritative" in l for l in s.trace))
    out.append(("J1 prepared-epoch renew ignored", ok,
                f"committed={r1.committed} lease_exp={r1.lease_exp}"))

    # J2: forged renew while coordinator dead (no legitimate renews):
    # lease must stay at its initial value.
    s = fresh()
    s.sched = [("crash_coord", 0, None), ("inject_renew", 2, 1, 1)]
    s.run()
    r1 = s.robots[0]
    ok = (r1.committed == 0 and r1.lease_exp == LEASE)
    out.append(("J2 renew with dead coordinator extends nothing", ok,
                f"committed={r1.committed} lease_exp={r1.lease_exp}"))

    # J3: forged renew for an obsolete epoch after a real commit, then
    # coordinator dies: lease frozen at the last legitimate value.
    s = fresh()
    s.sched = [("propose", 1, 1), ("crash_coord", 4, None),
               ("inject_renew", 5, 1, 0)]
    s.run()
    r1 = s.robots[0]
    ok = (r1.committed == 1 and r1.lease_exp == 4 + LEASE)
    out.append(("J3 obsolete-epoch renew extends nothing", ok,
                f"committed={r1.committed} lease_exp={r1.lease_exp}"))
    return out


def main():
    protos = ["broadcast", "2pc", "efrs"]
    all_sched = schedules()
    print(f"fleet-checker-t11: n={N} horizon={HORIZON} lease={LEASE} "
          f"schedules={len(all_sched)} window={VOTE_WINDOW_TICKS} "
          f"retry_delay={RETRY_DELAY_TICKS}")
    results = {}
    for p in protos:
        results[p] = {}
        for si, s in enumerate(all_sched):
            plans = ["stale"] if si == 5 else ["honest"]
            for plan in plans:
                sim = Sim(p, s, motion_plan=plan)
                results[p][(si, plan)] = sim.run()
    for p in protos:
        print(f"--- {p} (T0 schedules, rerun) ---")
        for key in sorted(results[p]):
            viols = results[p][key]
            kinds = sorted({k for k, _ in viols})
            print(f"  sched{key}: {len(viols)} violations {kinds}")
    print("=== T1.2 systematic (safety + EVENTUAL_HEAL liveness) ===")
    t12 = schedules_t12()
    for p in protos:
        print(f"--- {p} ---")
        for (name, s, live, conv, hor) in t12:
            want = live if p == "efrs" else None
            sim = Sim(p, s, motion_plan="honest", horizon=hor)
            viols = sim.run(live_expected=want,
                            converge=(conv and p == "efrs"))
            kinds = sorted({k for k, _ in viols})
            cm = sorted(e for (_, e) in sim.coord.commit_log)
            ab = len(sim.coord.abort_log)
            print(f"  {name}: {len(viols)} violations {kinds} "
                  f"commits={cm} aborts={ab} gens={dict(sim.coord.gen)}")
    print("=== G-c miss-then-dark HOLD regression (exact assertions) ===")
    for name, ok, detail in regression_miss_commit_hold():
        print(f"  {'PASS' if ok else 'FAIL'} {name} [{detail}]")
    print("=== §J contact-sync regression (exact assertions) ===")
    for name, ok, detail in regression_contact_sync():
        print(f"  {'PASS' if ok else 'FAIL'} {name} [{detail}]")
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
    kinds = ["COMMIT", "PREPARE", "VOTE", "RENEW", "ABORT", "ACK"]
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
                          r.choice(kinds)))
        if r.random() < 0.3:
            sched.append(("delay_kind", r.randrange(2, 9),
                          r.choice(kinds), r.randrange(2, 6)))
        if r.random() < 0.2:
            sched.append(("dup_kind", r.randrange(2, 9),
                          r.choice(["COMMIT", "PREPARE", "VOTE",
                                    "ABORT"])))
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
