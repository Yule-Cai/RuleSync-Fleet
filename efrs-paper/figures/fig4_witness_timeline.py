"""Fig4: Gazebo witness timeline (real timestamps from T1/Q evidence).
T1 witness: R3 partitioned t=2->25 s; epoch 1 (north KEEP_OUT x in
[4,8], y in [0,2]) proposed t=5 s; R3 lease-HELD 112x; heal t=25 s;
reconcile (epoch 1 observed); egress south <=3.0 s; detour; resume.
T13a Q: same shape; R3 lease-HELD 112-113x; egress <=3.1 s;
detour (y -> -1.5); runner stale 58-130 ms. 2PC contrast: 40.4 s
straight-through, 95 in-zone samples (T1 wit-2pc6/7/8).
Timeline below uses the T1 origins (t=2/5/25 s); T13a bounds annotated.
"""
import matplotlib
matplotlib.use("PDF")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 7, "font.family": "sans-serif"})
fig, ax = plt.subplots(figsize=(7.0, 2.9))
ax.set_xlim(0, 49)
ax.set_ylim(0, 4.4)
ax.set_xlabel("scenario time (s)", fontsize=7)
ax.set_yticks([])
for spine in ("top", "right", "left"):
    ax.spines[spine].set_visible(False)

# partition band t=2..25
ax.axvspan(2, 25, 0.30, 0.72, color="#d9d9d9", alpha=1.0, zorder=0)
ax.text(13.5, 2.9, "R3 partitioned (t = 2-25 s): 112-113 lease-HELDs, "
        "zero motion", ha="center", fontsize=6.5)
# markers
events = [
    (2, 1.6, "partition\nonset"),
    (5, 1.6, "epoch 1\nproposed"),
    (25, 1.6, "heal +\nreconcile\n(epoch 1 obs.)"),
    (28.1, 1.6, "egress south\n<=3.1 s"),
    (33, 1.6, "detour\n(y -> -1.5)"),
    (40, 1.6, "resume\nto goal"),
]
for t, y, lab in events:
    ax.plot([t, t], [0.4, 1.35], color="black", lw=0.9)
    ax.text(t, 0.32, lab, ha="center", va="top", fontsize=6)
# main timeline
ax.plot([0, 45], [1.9, 1.9], color="black", lw=1.0)
# 2PC contrast lane
ax.plot([0, 45], [3.6, 3.6], color="black", lw=0.7)
ax.text(0.3, 3.8, "2PC contrast (same scenario): R3 never commits, "
        "drives stale route straight through\n(95 in-zone samples, "
        "stale 40.4 s)", ha="left", va="bottom", fontsize=6.5)
ax.text(0.3, 2.05, "EFRS R3:", ha="left", va="bottom", fontsize=6.5,
        style="italic")

ax.text(22.5, 0.02,
        "Fig. 4. Physical witness timeline (real origins; T13a bounds).",
        ha="center", fontsize=6.5, style="italic",
        transform=ax.transAxes)
fig.subplots_adjust(left=0.04, right=0.98, top=0.92, bottom=0.22)
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig4_witness_timeline.pdf")
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig4_witness_timeline.svg")
print("fig4 ok")
