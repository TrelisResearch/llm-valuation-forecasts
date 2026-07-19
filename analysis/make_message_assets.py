"""Two X-ready message PNGs:
  assets/growth_rates.png - forecast growth vs realized, per company
  assets/tail_beliefs.png - log-log survival curves: power law vs lognormal

Usage: uv run analysis/make_message_assets.py
"""

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"

T = {"page": "#f9f9f7", "surface": "#fcfcfb", "ink": "#0b0b0b", "sub": "#52514e",
     "muted": "#898781", "grid": "#e1e0d9", "blue": "#2a78d6", "actual": "#e34948",
     "band": "#e1e0d9"}

DATA = json.loads((ROOT / "site" / "data.json").read_text())
SHORT = {"Alphabet (Google)": "Alphabet", "Meta Platforms": "Meta"}


def footer(fig):
    fig.text(0.07, 0.032, "26 models, cutoffs Sep 2021 - Feb 2026 · no internet · "
             "research.trelis.com/llm-valuation-forecasts", color=T["muted"], fontsize=9)
    fig.text(0.955, 0.032, "@ronankmcgovern", color=T["muted"], fontsize=9, ha="right")


def cohort_cagr():
    """Log-linear slope of each cohort's forecast fan, per company."""
    rows = defaultdict(list)
    for c in DATA["cohorts"]:
        rows[(c["company"], c["cohort"])].append((int(c["target"][:4]), c["median"]))
    out = defaultdict(list)
    for (company, cohort), pts in rows.items():
        pts.sort()
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [math.log(p[1]) for p in pts]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        slope = (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                 / sum((x - mx) ** 2 for x in xs))
        out[company].append(math.exp(slope) - 1)
    return out


def render_growth():
    cagr = cohort_cagr()
    companies = ["NVIDIA", "Alphabet (Google)", "Meta Platforms", "OpenAI", "Anthropic"]
    realized = {}
    for c in companies:
        gt = DATA["ground_truth"][c]
        realized[c] = (gt["latest"] / gt["2024-01-01"]) ** (1 / 2.5) - 1

    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=125)
    fig.patch.set_facecolor(T["page"])
    fig.subplots_adjust(left=0.16, right=0.94, top=0.74, bottom=0.14)
    fig.text(0.07, 0.945, "AI models forecast like a finance textbook",
             color=T["ink"], fontsize=20, fontweight="bold", va="top")
    fig.text(0.07, 0.875,
             "Growth rates implied by each cutoff cohort's valuation forecasts (blue)\n"
             "match required rates of return: ~9%/yr for public equities, venture rates for startups.\n"
             "Realized growth Jan 2024 → Jul 2026 (red) blew through all of it.",
             color=T["sub"], fontsize=11.5, va="top")
    ax.set_facecolor(T["surface"])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(axis="x", color=T["grid"], linewidth=0.8)
    ax.set_axisbelow(True)

    ys = range(len(companies))[::-1]
    ax.set_xscale("symlog", linthresh=0.35)
    ax.set_xlim(0, 4.6)
    ax.set_ylim(-1.0, len(companies) - 0.4)
    # theory bands, labeled inside the bottom of the plot
    ax.axvspan(0.07, 0.10, color=T["band"], alpha=0.7, zorder=0)
    ax.text(0.085, -0.72, "public equity\nrequired return", ha="center",
            fontsize=8.5, color=T["muted"])
    ax.axvspan(0.15, 0.30, color=T["band"], alpha=0.45, zorder=0)
    ax.text(0.215, -0.72, "late-stage venture\nhurdle rates", ha="center",
            fontsize=8.5, color=T["muted"])

    for y, c in zip(ys, companies):
        vals = sorted(cagr[c])
        ax.plot([min(vals), max(vals)], [y, y], color=T["blue"], linewidth=3,
                solid_capstyle="round", alpha=0.45)
        ax.plot(statistics.median(vals), y, "o", color=T["blue"], markersize=11,
                markeredgecolor=T["surface"], markeredgewidth=2)
        ax.plot(realized[c], y, "o", color=T["actual"], markersize=11,
                markeredgecolor=T["surface"], markeredgewidth=2)
        gap = realized[c] - statistics.median(vals)
        ax.annotate("", xy=(realized[c] - 0.012, y), xytext=(max(vals) + 0.012, y),
                    arrowprops={"arrowstyle": "->", "color": T["muted"], "lw": 1.2,
                                "shrinkA": 0, "shrinkB": 0})
    ax.set_yticks(list(ys))
    ax.set_yticklabels([SHORT.get(c, c) for c in companies], fontsize=12.5,
                       color=T["ink"])
    ax.set_xticks([0, 0.1, 0.25, 0.5, 1, 2, 4])
    ax.set_xticklabels(["0%", "10%", "25%", "50%", "100%", "200%", "400%"])
    ax.minorticks_off()
    ax.tick_params(colors=T["muted"], length=0, labelsize=10.5)
    ax.set_xlabel("annual growth rate (log scale)", color=T["muted"], fontsize=10)

    handles = [plt.Line2D([], [], marker="o", linestyle="", color=T["blue"],
                          markersize=10, label="model forecasts (median, range across cohorts)"),
               plt.Line2D([], [], marker="o", linestyle="", color=T["actual"],
                          markersize=10, label="realized (Jan 2024 → Jul 2026)")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.62, 0.97),
               frameon=False, fontsize=10, labelcolor=T["sub"])
    footer(fig)
    fig.savefig(ASSETS / "growth_rates.png", facecolor=T["page"])
    plt.close(fig)
    print("wrote assets/growth_rates.png")


def render_tails():
    path = sorted((ROOT / "results").glob("tails_*.jsonl"))[-1]
    recs = [json.loads(l) for l in path.read_text().splitlines()]
    by = defaultdict(list)
    for r in recs:
        if r.get("parsed"):
            by[(r["subject"], r["model"])].append(r)

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 7.2), dpi=125)
    fig.patch.set_facecolor(T["page"])
    fig.subplots_adjust(left=0.09, right=0.965, top=0.70, bottom=0.13, wspace=0.25)
    fig.text(0.07, 0.945, "AI models believe startups are power-law, stocks are lognormal",
             color=T["ink"], fontsize=19, fontweight="bold", va="top")
    fig.text(0.07, 0.875,
             "Each model's stated probability that the 2030 value exceeds k× today's, on log-log axes.\n"
             "A straight line is a power law. For Anthropic the models draw straight lines with tail exponent "
             "α ≈ 1.4–2.0 —\nthe same range the venture-returns literature finds. For NVIDIA the curves bend: "
             "thinner, lognormal-like tails.",
             color=T["sub"], fontsize=11, va="top")

    panels = [("named-anthropic", "Anthropic ($965B today) — straight = power law"),
              ("nvidia", "NVIDIA ($5.1T today) — curved = lognormal")]
    for ax, (subj, title) in zip(axes, panels):
        ax.set_facecolor(T["surface"])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.grid(color=T["grid"], linewidth=0.7)
        ax.set_axisbelow(True)
        models = sorted({m for (s2, m) in by if s2 == subj})
        for i, m in enumerate(models):
            rs = by[(subj, m)]
            ks = rs[0]["ks"]
            med = {k: statistics.median(float(str(r["parsed"][str(k)]).rstrip("% "))
                                        for r in rs) for k in ks}
            pts = [(k, p) for k, p in med.items() if p > 0]
            shade = 0.35 + 0.65 * i / max(len(models) - 1, 1)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-",
                    color=T["blue"], alpha=shade, linewidth=2, markersize=5,
                    markeredgecolor=T["surface"], markeredgewidth=1)
            ax.annotate(m.split("/")[1], xy=pts[-1],
                        xytext=(5, 0), textcoords="offset points",
                        fontsize=7.5, color=T["sub"], alpha=max(shade, 0.6))
        ax.set_xscale("log")
        ax.set_yscale("log")
        ticks = rs[0]["ks"] if (rs := by[(subj, models[0])]) else []
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{k:g}×" for k in ticks])
        ax.set_xlim(ticks[0] * 0.85, ticks[-1] * 2.6)  # room for direct labels
        ax.minorticks_off()
        ax.set_title(title, color=T["ink"], fontsize=11.5, fontweight="bold", loc="left")
        ax.set_xlabel("multiple of today's value (k)", color=T["muted"], fontsize=10)
        ax.set_ylabel("P(2030 value > k×)  %", color=T["muted"], fontsize=10)
        ax.tick_params(colors=T["muted"], labelsize=9, length=0, which="both")
    footer(fig)
    fig.savefig(ASSETS / "tail_beliefs.png", facecolor=T["page"])
    plt.close(fig)
    print("wrote assets/tail_beliefs.png")


if __name__ == "__main__":
    render_growth()
    render_tails()
