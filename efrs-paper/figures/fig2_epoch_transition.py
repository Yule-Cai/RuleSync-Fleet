"""Fig2: rule-epoch transition schematic with frozen budgets.
Budgets: lease 1000 ms, guard 50 ms, jitter 250 ms, B_real 1300 ms,
vote timeout 1500 ms, heartbeat/renew 100 ms. Schematic (not a trace);
values are the frozen engineering budgets from EFRS_T1_PREREGISTRATION.
"""
import matplotlib
matplotlib.use("PDF")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 7, "font.family": "sans-serif"})
fig, ax = plt.subplots(figsize=(7.0, 2.6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 4.2)
ax.axis("off")

ax.plot([0.5, 9.5], [2.6, 2.6], color="black", lw=1.0)
for t, lab in ((1.0, "0"), (3.0, "T_c\nCOMMIT(e+1)\nWAL-append"), (8.6, "time")):
    ax.plot([t, t], [2.5, 2.7], color="black", lw=0.9)
    ax.text(t, 2.15, lab, ha="center", va="top", fontsize=6.5)

# lease window of epoch e (granted before Tc, lives 1000 ms)
ax.annotate("", xy=(1.0, 3.3), xytext=(0.2, 3.3),
            arrowprops=dict(arrowstyle="<|-|>", mutation_scale=9, lw=0.8))
ax.text(0.6, 3.5, "lease(e) 1000 ms", ha="center", fontsize=6.5)
# obsolete ACCEPTs region after Tc, bounded by B_real (x in seconds)
ax.axvspan(3.0, 4.3, 0.35, 0.62, color="#d9d9d9",
           alpha=1.0, zorder=0)
ax.text(3.65, 2.95, "obsolete-epoch ACCEPTs\nend here at latest", ha="center",
        fontsize=6.5)
# B_real bracket
ax.annotate("", xy=(4.3, 2.35), xytext=(3.0, 2.35),
            arrowprops=dict(arrowstyle="<|-|>", mutation_scale=9, lw=0.8))
ax.text(3.65, 1.7, "B_real = 1000 + 50 + 250 = 1300 ms\n"
        "(lease + fence-scheduling guard + in-flight drain)",
        ha="center", fontsize=6.5)
# HOLD + reconcile markers (HOLD at worst-case lease expiry Tc+1.0 s)
ax.plot([4.0, 4.0], [0.7, 1.3], color="black", lw=0.9)
ax.text(4.0, 0.55, "HOLD on\nlease expiry", ha="center", fontsize=6.5)
ax.plot([7.6, 7.6], [0.7, 1.3], color="black", lw=0.9)
ax.text(7.6, 0.55, "reconcile_rep\napplied → resume", ha="center",
        fontsize=6.5)

ax.text(5.0, 0.02,
        "Fig. 2. Epoch transition with frozen budgets (schematic; budgets are "
        "stated assumptions, not measurements).",
        ha="center", fontsize=6.5, style="italic")
fig.tight_layout(pad=0.4)
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig2_epoch_transition.pdf")
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig2_epoch_transition.svg")
print("fig2 ok")
