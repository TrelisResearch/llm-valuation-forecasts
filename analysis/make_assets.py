"""Render X-shareable assets from site/data.json:
  assets/headline_light.png, assets/headline_dark.png  (1600x900)
  assets/openai_light.png                              (single-panel hero)
  assets/headline_reveal.mp4                           (cohorts appear in cutoff order)

Usage: uv run analysis/make_assets.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

THEMES = {
    "light": {"page": "#f9f9f7", "surface": "#fcfcfb", "ink": "#0b0b0b",
              "sub": "#52514e", "muted": "#898781", "grid": "#e1e0d9",
              "actual": "#e34948",
              "cohorts": {"2021": "#86b6ef", "2023": "#5598e7", "2024": "#2a78d6",
                          "2025": "#1c5cab", "2026": "#0d366b"}},
    "dark": {"page": "#0d0d0d", "surface": "#1a1a19", "ink": "#ffffff",
             "sub": "#c3c2b7", "muted": "#898781", "grid": "#2c2c2a",
             "actual": "#e66767",
             "cohorts": {"2021": "#184f95", "2023": "#256abf", "2024": "#3987e5",
                         "2025": "#6da7ec", "2026": "#b7d3f6"}},
}

DATA = json.loads((ROOT / "site" / "data.json").read_text())
COMPANIES = ["OpenAI", "Anthropic", "NVIDIA", "Alphabet (Google)", "Meta Platforms"]
SHORT = {"Alphabet (Google)": "Alphabet", "Meta Platforms": "Meta"}
COHORT_YEARS = sorted({c["cohort"] for c in DATA["cohorts"]})


def year_frac(iso: str) -> float:
    y, m = iso.split("-")[:2]
    return int(y) + (int(m) - 1) / 12


def fmt_b(v: float) -> str:
    return f"${v / 1000:.0f}T" if v >= 1000 else f"${v:.0f}B"


def cohort_series(company: str, cohort: str) -> tuple[list, list]:
    rows = sorted((c for c in DATA["cohorts"]
                   if c["company"] == company and c["cohort"] == cohort),
                  key=lambda c: c["target"])
    return ([year_frac(c["target"]) for c in rows], [c["median"] for c in rows])


def actual_series(company: str) -> tuple[list, list]:
    gt = DATA["ground_truth"].get(company, {})
    pts = [(year_frac(k), v) for k, v in gt.items()
           if isinstance(v, (int, float)) and k not in ("latest",)]
    if isinstance(gt.get("latest"), (int, float)):
        pts.append((year_frac(DATA["ground_truth"].get("as_of", "2026-07-01")), gt["latest"]))
    pts.sort()
    return [p[0] for p in pts], [p[1] for p in pts]


def style_axis(ax, t, ylim):
    ax.set_yscale("log")
    ax.set_xlim(2023.7, 2030.3)
    ax.set_ylim(*ylim)
    ax.set_facecolor(t["surface"])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(axis="y", color=t["grid"], linewidth=0.7)
    ax.set_xticks([2024, 2026, 2028, 2030])
    ax.tick_params(colors=t["muted"], labelsize=9, length=0)
    yticks = [10, 100, 1000, 5000]
    ax.set_yticks([v for v in yticks if ylim[0] <= v <= ylim[1]])
    ax.set_yticklabels([fmt_b(v) for v in yticks if ylim[0] <= v <= ylim[1]])
    ax.minorticks_off()


def draw_panel(ax, company, t, cohort_alpha=None, line_frac=1.0, actual_on=True):
    """cohort_alpha: {year: alpha}; line_frac: fraction of each line drawn (for animation)."""
    lo, hi = 1e9, 0
    for y in COHORT_YEARS:
        xs, ys = cohort_series(company, y)
        if ys:
            lo, hi = min(lo, min(ys)), max(hi, max(ys))
    axs, ays = actual_series(company)
    if ays:
        lo, hi = min(lo, min(ays)), max(hi, max(ays))
    style_axis(ax, t, (lo * 0.5, hi * 2.5))
    ax.set_title(SHORT.get(company, company), color=t["ink"], fontsize=12,
                 fontweight="bold", loc="left", pad=6)

    for y in COHORT_YEARS:
        xs, ys = cohort_series(company, y)
        if not xs:
            continue
        alpha = 1.0 if cohort_alpha is None else cohort_alpha.get(y, 0.0)
        if alpha <= 0:
            continue
        n = max(2, int(len(xs) * line_frac)) if alpha == cohort_alpha_last(cohort_alpha, y) else len(xs)
        ax.plot(xs[:n], ys[:n], color=t["cohorts"][y], linewidth=2.2, alpha=alpha,
                solid_capstyle="round")
    if actual_on and axs:
        ax.plot(axs, ays, color=t["actual"], linewidth=2.8, marker="o", markersize=5,
                markeredgecolor=t["surface"], markeredgewidth=1.4, zorder=5)


def cohort_alpha_last(cohort_alpha, y):
    if cohort_alpha is None:
        return None
    active = [k for k, v in cohort_alpha.items() if v > 0]
    return cohort_alpha[y] if active and y == max(active) else None


def make_figure(t, title, subtitle):
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor(t["page"])
    fig.subplots_adjust(left=0.055, right=0.975, top=0.76, bottom=0.10,
                        hspace=0.42, wspace=0.22)
    fig.text(0.055, 0.945, title, color=t["ink"], fontsize=21, fontweight="bold", va="top")
    fig.text(0.055, 0.885, subtitle, color=t["sub"], fontsize=11.5, va="top")
    fig.text(0.055, 0.033, "No internet access · one question per model/date · 3-sample medians · "
             "log scale, USD · cutoffs as documented by providers",
             color=t["muted"], fontsize=9)
    fig.text(0.975, 0.033, "TrelisResearch/llm-valuation-forecasts", color=t["muted"],
             fontsize=9, ha="right")
    return fig, axes


def legend_on(fig, t):
    handles = [plt.Line2D([], [], color=t["cohorts"][y], linewidth=2.5,
                          label=f"cutoff {y}") for y in COHORT_YEARS]
    handles.append(plt.Line2D([], [], color=t["actual"], linewidth=2.8, marker="o",
                              markersize=5, label="actual"))
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.975, 0.86),
               ncol=len(handles), frameon=False, fontsize=10,
               labelcolor=t["sub"])


TITLE = "What does AI think AI companies are worth?"
SUBTITLE = ("Models with knowledge cutoffs from Sep 2021 (light) to Feb 2026 (dark) forecast "
            "valuations for Jan 1, 2024–2030 — red shows what actually happened.")


def render_static(mode: str) -> None:
    t = THEMES[mode]
    fig, axes = make_figure(t, TITLE, SUBTITLE)
    slots = list(axes.flat)
    for ax, company in zip(slots, COMPANIES):
        draw_panel(ax, company, t)
    slots[-1].axis("off")
    legend_on(fig, t)
    out = ASSETS / f"headline_{mode}.png"
    fig.savefig(out, facecolor=t["page"])
    plt.close(fig)
    print("wrote", out)


def render_single(company: str, mode: str) -> None:
    t = THEMES[mode]
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=125)
    fig.patch.set_facecolor(t["page"])
    fig.subplots_adjust(left=0.08, right=0.96, top=0.76, bottom=0.10)
    fig.text(0.08, 0.94, f"What did AI models think {SHORT.get(company, company)} would be worth?",
             color=t["ink"], fontsize=19, fontweight="bold", va="top")
    fig.text(0.08, 0.87, SUBTITLE, color=t["sub"], fontsize=11, va="top", wrap=True)
    fig.text(0.08, 0.035, "No internet · one question per model/date · 3-sample medians · log scale",
             color=t["muted"], fontsize=9)
    fig.text(0.96, 0.035, "TrelisResearch/llm-valuation-forecasts", color=t["muted"],
             fontsize=9, ha="right")
    draw_panel(ax, company, t)
    ax.set_title("")
    legend_on(fig, t)
    out = ASSETS / f"{SHORT.get(company, company).lower()}_{mode}.png"
    fig.savefig(out, facecolor=t["page"])
    plt.close(fig)
    print("wrote", out)


def render_video(mode: str = "light", fps: int = 30) -> None:
    t = THEMES[mode]
    hold, per_cohort, draw_frames = int(0.8 * fps), int(1.6 * fps), int(1.0 * fps)
    frames = []  # (cohort_alpha, line_frac, actual_on, caption)
    for i, y in enumerate(COHORT_YEARS):
        for f in range(per_cohort):
            alpha = {c: 1.0 for c in COHORT_YEARS[:i]}
            alpha[y] = 1.0
            frac = min(1.0, f / draw_frames)
            frames.append((alpha, frac, False, f"models with knowledge up to {y} …"))
        frames += [(dict.fromkeys(COHORT_YEARS[:i + 1], 1.0), 1.0, False,
                    f"models with knowledge up to {y} …")] * hold
    frames += [(dict.fromkeys(COHORT_YEARS, 1.0), 1.0, True,
                "… and what actually happened (red)")] * (4 * hold)

    fig, axes = make_figure(t, TITLE, SUBTITLE)
    legend_on(fig, t)
    caption = fig.text(0.82, 0.28, "", color=t["ink"], fontsize=14, fontweight="bold",
                       ha="center", wrap=True)
    out = ASSETS / "headline_reveal.mp4"
    writer = FFMpegWriter(fps=fps, bitrate=3000)
    slots = list(axes.flat)
    with writer.saving(fig, out, dpi=100):
        for alpha, frac, actual_on, cap in frames:
            for ax, company in zip(slots, COMPANIES):
                ax.clear()
                draw_panel(ax, company, t, cohort_alpha=alpha, line_frac=frac,
                           actual_on=actual_on)
            slots[-1].axis("off")
            caption.set_text(cap)
            writer.grab_frame(facecolor=t["page"])
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    render_static("light")
    render_static("dark")
    render_single("OpenAI", "light")
    render_single("Anthropic", "light")
    render_video("light")
