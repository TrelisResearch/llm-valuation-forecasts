"""Build site/probe.json from the latest probe run + point-estimate medians.

Re-parses records whose FINAL JSON had commas inside numbers.
"""

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent

ANCHORS = {"named-openai": 852, "named-anthropic": 965,
           "anon-frontier": 950, "anon-midsize": 20}
LABELS = {"named-openai": "OpenAI (named)", "named-anthropic": "Anthropic (named)",
          "anon-frontier": "Frontier lab (name blinded, $950B)",
          "anon-midsize": "Late-stage AI co (name blinded, $20B)"}
POINT_COMPANY = {"named-openai": "OpenAI", "named-anthropic": "Anthropic"}


def parse(text: str) -> dict | None:
    m = re.findall(r"FINAL:\s*(\{.*?\})", text or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(re.sub(r"(\d),(\d)", r"\1\2", m[-1]))
        return d if all(k in d for k in ("p10", "p50", "p90", "p_below")) else None
    except json.JSONDecodeError:
        return None


path = sorted((ROOT / "results").glob("probe_*.jsonl"))[-1]
recs = [json.loads(l) for l in path.read_text().splitlines()]
by = defaultdict(list)
for r in recs:
    p = r.get("parsed") or parse(r.get("response"))
    if p:
        by[(r["model"], r["cutoff"], r["question"])].append(p)

data = json.loads((ROOT / "site" / "data.json").read_text())
point_2030 = {(p["model"], p["company"]): p["median"]
              for p in data["points"] if p["target"] == "2030-01-01"}

rows = []
for (model, cutoff, q), ps in sorted(by.items()):
    row = {"model": model, "cutoff": cutoff, "question": q, "n": len(ps),
           "p10": statistics.median(p["p10"] for p in ps),
           "p50": statistics.median(p["p50"] for p in ps),
           "p90": statistics.median(p["p90"] for p in ps),
           "p_below": statistics.median(p["p_below"] for p in ps)}
    if q in POINT_COMPANY:
        row["point_estimate"] = point_2030.get((model, POINT_COMPANY[q]))
    rows.append(row)

out = {"run": path.name, "anchors": ANCHORS, "labels": LABELS, "rows": rows,
       "target": "2030-01-01"}
(ROOT / "site" / "probe.json").write_text(json.dumps(out))
print(f"wrote site/probe.json ({len(rows)} rows from {path.name})")
