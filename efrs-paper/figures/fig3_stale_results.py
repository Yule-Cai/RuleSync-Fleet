"""Fig3: worst-cell stale-motion authorization (log scale, real numbers).
EFRS campaign maxima vs B_real budget vs controls (all ms):
- EFRS det-matrix max 153.8 (T1 report §3-robot matrix)
- EFRS 30x max 181.3 (T1 report §30x)
- EFRS 5-robot max 163.1 (T1 report §5-robot, P41)
- EFRS W-HEAL max 263.2 (T13a final §8-11)
- EFRS M max cell 552 (T13a final §14 "cell maxima 0-552 ms")
- B_real 1300 (budget line, not a measurement)
- A3 renewal-bug control 7792.2 (T13a final §17, corrected run)
- plain-2PC worst cell 12700 (T1 report: 2PC up to 12.7 s)
"""
import matplotlib
matplotlib.use("PDF")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"font.size": 7, "font.family": "sans-serif"})
fig, ax = plt.subplots(figsize=(7.0, 2.7))

labels = ["EFRS\nmatrix", "EFRS\n30x", "EFRS\n5-robot", "EFRS\nW-HEAL",
          "EFRS\nM worst", "A3 control\n(no adopt)", "2PC worst\ncell"]
values = [153.8, 181.3, 163.1, 263.2, 552.0, 7792.2, 12700.0]
colors = ["#6a6a6a"] * 5 + ["#b3b3b3"] * 2

x = np.arange(len(labels))
bars = ax.bar(x, values, color=colors, edgecolor="black", lw=0.7, width=0.62)
ax.set_yscale("log")
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=6.5)
ax.set_ylabel("worst stale authorization (ms, log)", fontsize=7)
ax.axhline(1300, color="black", lw=0.9, ls=(0, (3, 2)))
ax.text(len(labels) - 0.5, 1300 * 1.25, "B_real = 1300 ms (budget)",
        ha="right", va="bottom", fontsize=6.5)
for b, v in zip(bars, values):
    ax.text(b.get_x() + b.get_width() / 2, v * 1.18, f"{v:g}",
            ha="center", va="bottom", fontsize=6.5)
ax.set_ylim(60, 30000)
ax.text(0.5, 0.02,
        "Fig. 3. Worst-cell stale-motion authorization per campaign "
        "(authorization, not stopping).",
        ha="center", fontsize=6.5, style="italic",
        transform=ax.transAxes)
fig.tight_layout(pad=0.4)
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig3_stale_results.pdf")
fig.savefig("/Users/yulecai/Desktop/RuleSync-Fleet/efrs-paper/figures/fig3_stale_results.svg")
print("fig3 ok")
