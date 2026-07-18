"""Aggregate raw run JSONL into site/data.json.

Per (company, model, target): median/min/max over samples.
Cutoff cohorts = cutoff year (2021, 2023, 2024, 2025, 2026); cohort series =
median across all models in the cohort. Ground truth merged from
analysis/ground_truth.json.

Usage: uv run analysis/aggregate.py results/run_XXXX.jsonl [more.jsonl ...]
Later files fill in records that failed in earlier ones (retry runs).
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent


def main() -> None:
    run_path = Path(sys.argv[1])
    recs = []
    for arg in sys.argv[1:]:
        recs += [json.loads(l) for l in Path(arg).read_text().splitlines()]
    ok = [r for r in recs if r.get("valuation_billions") is not None]
    n_err = sum("error" in r for r in recs)
    n_unparsed = len(recs) - len(ok) - n_err
    print(f"{len(recs)} records: {len(ok)} ok, {n_err} errors, {n_unparsed} unparsed, "
          f"{sum(r.get('nudged', False) for r in ok)} nudged")

    cfg = yaml.safe_load((ROOT / "config" / "models.yaml").read_text())
    meta = {e["id"]: {**e, "family": fam}
            for fam, entries in cfg["families"].items() for e in entries}

    by_key = defaultdict(list)
    for r in ok:
        by_key[(r["company"], r["model"], r["target_date"])].append(r["valuation_billions"])

    points = []
    for (company, model, target), vals in sorted(by_key.items()):
        points.append({
            "company": company, "model": model, "target": target,
            "median": statistics.median(vals),
            "min": min(vals), "max": max(vals), "n": len(vals),
            "cutoff": str(meta[model]["cutoff"]), "family": meta[model]["family"],
        })

    # cohort = cutoff year; cohort value = median of model medians
    cohort_vals = defaultdict(list)
    for p in points:
        cohort_vals[(p["company"], p["cutoff"][:4], p["target"])].append(p["median"])
    cohorts = [{"company": c, "cohort": y, "target": t,
                "median": statistics.median(v), "n_models": len(v)}
               for (c, y, t), v in sorted(cohort_vals.items())]

    gt_path = ROOT / "analysis" / "ground_truth.json"
    ground_truth = json.loads(gt_path.read_text()) if gt_path.exists() else {}

    models = [{"id": mid, "family": m["family"], "cutoff": str(m["cutoff"]),
               "release": str(m.get("release", ""))}
              for mid, m in meta.items() if any(p["model"] == mid for p in points)]

    out = {
        "run": run_path.name,
        "companies": sorted({p["company"] for p in points}),
        "targets": sorted({p["target"] for p in points}),
        "models": sorted(models, key=lambda m: (m["family"], m["cutoff"])),
        "points": points,
        "cohorts": cohorts,
        "ground_truth": ground_truth,
    }
    out_path = ROOT / "site" / "data.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out))
    print(f"Wrote {out_path} ({len(points)} points, {len(cohorts)} cohort rows)")


if __name__ == "__main__":
    main()
