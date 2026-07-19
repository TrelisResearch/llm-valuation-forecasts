"""Build site/calib.json: bucket shares per model + overall + by kind."""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
GT = json.loads((ROOT / "analysis" / "ground_truth.json").read_text())
ORDER = ["below p10", "p10-p50", "p50-p90", "above p90"]


def parse(text):
    m = re.findall(r"FINAL:\s*(\{.*?\})", text or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(re.sub(r"(\d),(\d)", r"\1\2", m[-1]))
        return d if all(k in d for k in ("p10", "p50", "p90")) else None
    except json.JSONDecodeError:
        return None


path = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted((ROOT / "results").glob("calib_*.jsonl"))[-1]
cells = []
for line in path.read_text().splitlines():
    r = json.loads(line)
    p = r.get("parsed") or parse(r.get("response"))
    if not p or not all(isinstance(p.get(k), (int, float)) and p[k] > 0
                        for k in ("p10", "p50", "p90")):
        continue
    v = GT[r["company"]]["latest" if r["target"] == "2026-07-01" else r["target"]]
    b = ("below p10" if v < p["p10"] else "p10-p50" if v <= p["p50"]
         else "p50-p90" if v <= p["p90"] else "above p90")
    cells.append({"model": r["model"], "kind": r["kind"], "bucket": b})


def shares(rows):
    c = Counter(r["bucket"] for r in rows)
    n = len(rows)
    return {"n": n, **{b: round(c.get(b, 0) / n, 3) for b in ORDER}}


out = {
    "run": path.name,
    "perfect": {"below p10": 0.10, "p10-p50": 0.40, "p50-p90": 0.40, "above p90": 0.10, "n": None},
    "overall": shares(cells),
    "by_kind": {k: shares([r for r in cells if r["kind"] == k]) for k in ("private", "public")},
    "by_model": {m: shares([r for r in cells if r["model"] == m])
                 for m in sorted({r["model"] for r in cells})},
}
(ROOT / "site" / "calib.json").write_text(json.dumps(out))
print("wrote site/calib.json,", len(cells), "cells")
