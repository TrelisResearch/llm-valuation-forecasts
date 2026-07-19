"""Score the hindsight-calibration probe: where did reality land in each
model's stated p10/p50/p90 distribution?

Calibrated forecaster: ~10% below p10, ~40% p10-p50, ~40% p50-p90, ~10% above p90.

Usage: uv run analysis/score_calibration.py [results/calib_X.jsonl]
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent

GT = json.loads((ROOT / "analysis" / "ground_truth.json").read_text())


def truth(company: str, target: str) -> float:
    return GT[company]["latest" if target == "2026-07-01" else target]


def parse(text: str) -> dict | None:
    m = re.findall(r"FINAL:\s*(\{.*?\})", text or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(re.sub(r"(\d),(\d)", r"\1\2", m[-1]))
        return d if all(k in d for k in ("p10", "p50", "p90")) else None
    except json.JSONDecodeError:
        return None


def bucket(v: float, p: dict) -> str:
    if v < p["p10"]:
        return "below p10"
    if v <= p["p50"]:
        return "p10-p50"
    if v <= p["p90"]:
        return "p50-p90"
    return "ABOVE p90"


paths = [Path(a) for a in sys.argv[1:]] or [sorted((ROOT / "results").glob("calib_*.jsonl"))[-1]]
cells = []
for path in paths:
    for line in path.read_text().splitlines():
        r = json.loads(line)
        p = r.get("parsed") or parse(r.get("response"))
        if not p or not all(isinstance(p[k], (int, float)) and p[k] > 0
                            for k in ("p10", "p50", "p90")):
            continue
        v = truth(r["company"], r["target"])
        cells.append({**r, "p": p, "actual": v, "bucket": bucket(v, p)})

ORDER = ["below p10", "p10-p50", "p50-p90", "ABOVE p90"]
print(f"{len(cells)} scored cells (target ~10/40/40/10)\n")

def show(label, rows):
    c = Counter(r["bucket"] for r in rows)
    n = len(rows)
    if not n:
        return
    print(f"{label:34s} " + " ".join(f"{b}:{c.get(b,0)/n:>4.0%}" for b in ORDER) + f"  n={n}")

show("ALL", cells)
print()
for kind in ("private", "public"):
    show(f"kind={kind}", [r for r in cells if r["kind"] == kind])
print()
for m in sorted({r["model"] for r in cells}):
    show(m, [r for r in cells if r["model"] == m])
print()
for t in sorted({r["target"] for r in cells}):
    show(f"target {t}", [r for r in cells if r["target"] == t])

# tail-shape: log-space symmetry of stated distributions (lognormal => ratio 1)
import math
ratios = defaultdict(list)
for r in cells:
    p = r["p"]
    if p["p10"] > 0 and p["p90"] > p["p50"] > p["p10"]:
        ratios[r["kind"]].append(math.log(p["p90"] / p["p50"]) / math.log(p["p50"] / p["p10"]))
print("\nlog-space right/left spread ratio (1 = lognormal-symmetric, >1 = heavier right tail):")
for k, v in ratios.items():
    v.sort()
    print(f"  {k:8s} median {v[len(v)//2]:.2f}  (n={len(v)})")
