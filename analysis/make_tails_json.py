"""Build site/tails.json: median survival probabilities per model/subject."""

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent

LABELS = {"named-anthropic": "Anthropic ($965B today)",
          "anon-midsize": "Unnamed $20B AI company",
          "nvidia": "NVIDIA ($5.1T today)"}

path = sorted((ROOT / "results").glob("tails_*.jsonl"))[-1]
recs = [json.loads(l) for l in path.read_text().splitlines()]
by = defaultdict(list)
for r in recs:
    if r.get("parsed"):
        by[(r["subject"], r["model"])].append(r)

subjects = {}
for (subj, model), rs in sorted(by.items()):
    ks = rs[0]["ks"]
    med = {str(k): statistics.median(float(str(r["parsed"][str(k)]).rstrip("% "))
                                     for r in rs) for k in ks}
    s = subjects.setdefault(subj, {"label": LABELS[subj], "ks": ks, "models": {}})
    s["models"][model] = med

(ROOT / "site" / "tails.json").write_text(json.dumps({"run": path.name, "subjects": subjects}))
print("wrote site/tails.json:", {k: len(v["models"]) for k, v in subjects.items()})
