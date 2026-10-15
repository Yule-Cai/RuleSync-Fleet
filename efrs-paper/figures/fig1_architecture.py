"""Fig1: EFRS architecture + authorization boundary (vector source).
Semantics from efrs-t13a/efrs_ros2/{coordinator,robot_agent,motion_fence}.py
and msgspec.py TOPICS. No decorative content.
"""
import matplotlib
matplotlib.use("PDF")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({"font.size": 7, "font.family": "sans-serif"})
fig, ax = plt.subplots(figsize=(7.0, 3.1))
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)
ax.axis("off")


def box(x, y, w, h, text, fc="white", ec="black", fs=7, style=None):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                       fc=fc, ec=ec, lw=0.9)
    ax.add_patch(b)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, linespacing=1.25)
    return b


def arrow(x1, y1, x2, y2, label=None, ls="-", lw=0.9):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                        mutation_scale=9, lw=lw, linestyle=ls,
                        color="black", shrinkA=1, shrinkB=2)
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.14, label, ha="center",
                va="bottom", fontsize=6)


# Coordinator (left)
box(0.2, 2.2, 2.5, 2.6,
    "Coordinator\nPREPARE / decide /\nCOMMIT / RENEW\nWAL (fsync first)", fs=7)
ax.text(1.45, 5.05, "coordinator process", ha="center", fontsize=6.5,
        style="italic")
# Robot agent (middle)
box(3.9, 2.2, 2.5, 2.6,
    "Robot agent (per robot)\nadopt / lease /\nreconcile-pull\nstate file", fs=7)
ax.text(5.15, 5.05, "agent process", ha="center", fontsize=6.5,
        style="italic")
# MotionFence (right)
box(7.5, 2.2, 2.3, 2.6,
    "MotionFence\n(per robot)\nCONJUNCTIVE GATE\n+ local ledger", fs=7,
    fc="#f2f2f2")
ax.text(8.65, 5.05, "fence process", ha="center", fontsize=6.5,
        style="italic")
# Actuator sink
box(7.5, 0.5, 2.3, 1.0, "actuator (cmd_vel)", fs=7, fc="#e6e6e6")

# Authorization boundary (dashed red line between fence and actuator)
ax.plot([7.3, 10.0], [1.7, 1.7], color="black", lw=0.9, ls=(0, (3, 2)))
ax.text(8.65, 1.82, "authorization boundary", ha="center", fontsize=6.5)

# Message arrows coordinator<->agent
arrow(2.7, 4.2, 3.9, 4.2, "PREPARE / COMMIT / RENEW / recon_rep")
arrow(3.9, 3.6, 2.7, 3.6, "vote / ACK / recon_req / state")
# agent -> fence (state)
arrow(6.4, 3.1, 7.5, 3.1, "agent state @5 Hz")
# motion commands into fence
arrow(6.4, 2.55, 7.5, 2.55, "motion_cmd (req_epoch, req_hash)")
# fence -> actuator
arrow(8.65, 2.2, 8.65, 1.5, None)
ax.text(8.85, 1.85, "release\niff gate passes", fontsize=6,
        va="center")
# fence events downward-left (log)
arrow(7.6, 2.2, 5.2, 1.1, None, ls=(0, (2, 2)))
ax.text(5.9, 1.15, "motion_event\n(HELD/REJECTED)", fontsize=6,
        ha="center")

ax.text(5.0, 0.15,
        "Fig. 1. Processes, topics, and the motion authorization boundary. "
        "Only the fence releases motion; baselines execute without the gate.",
        ha="center", fontsize=6.5, style="italic")
fig.tight_layout(pad=0.4)
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig1_architecture.pdf")
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig1_architecture.svg")
print("fig1 ok")
