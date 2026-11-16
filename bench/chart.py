"""Draws bench/results.png from bench/results/{agent,decision}.json: `make chart`."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BENCH = Path(__file__).parent
SERIES = {
    "agent": ("LLM agent (qwen3:1.7b)", "#2a78d6"),
    "decision": ("Decision model (d3:2b)", "#eb6834"),
}
DEPARTMENTS = ["help-desk", "it", "kadry", "human-resources", "other"]
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"

runs = {name: json.loads((BENCH / "results" / f"{name}.json").read_text()) for name in SERIES}
plt.rcParams.update(
    {
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": MUTED,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "svg.fonttype": "none",
    }
)
fig, (left, right) = plt.subplots(
    1, 2, figsize=(11, 4.2), width_ratios=[3, 1.3], facecolor=SURFACE, layout="constrained"
)

for i, (name, (label, color)) in enumerate(SERIES.items()):
    rows = runs[name]
    groups = [[r for r in rows if r["expected"] == d] for d in DEPARTMENTS] + [rows]
    share = [100 * sum(r["got"] == r["expected"] for r in g) / len(g) for g in groups]
    x = [j + (i - 0.5) * 0.38 for j in range(len(groups))]
    bars = left.bar(x, share, width=0.34, color=color, label=label)
    left.bar_label(bars, fmt="%.0f", padding=2, color=INK, fontsize=9)

    seconds = sorted(r["seconds"] for r in rows)
    median, p95 = seconds[len(seconds) // 2], seconds[int(len(seconds) * 0.95)]
    bar = right.bar([i], [median], width=0.5, color=color)
    right.bar_label(bar, labels=[f"{median:.1f} s\n(p95 {p95:.1f} s)"], padding=3, color=INK)

left.set_xticks(range(len(DEPARTMENTS) + 1), [*DEPARTMENTS, "all 100"])
left.set_ylim(0, 112)
left.set_yticks([0, 25, 50, 75, 100])
left.set_title("Messages routed to the right department (%)", loc="left", color=INK)
left.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncols=2)
right.set_xticks([0, 1], ["LLM agent", "Decision model"])
right.set_ylim(0, right.get_ylim()[1] * 1.3)
right.set_title("Median time per request (s)", loc="left", color=INK)
for ax in (left, right):
    ax.set_facecolor(SURFACE)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)

fig.savefig(BENCH / "results.png", dpi=110)
