"""Classify each elicited survival curve: power law (log-survival linear in
log k) vs lognormal-or-thinner (downward curvature).

Fit both forms to log10(P) vs log10(k); compare R^2 and report the curvature
of the quadratic fit (negative = thinner than power law).

Usage: uv run analysis/score_tails.py
"""

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent


def polyfit(xs, ys, deg):
    # least squares via normal equations (deg 1 or 2)
    n = len(xs)
    if deg == 1:
        mx, my = sum(xs) / n, sum(ys) / n
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        a = my - b * mx
        pred = [a + b * x for x in xs]
        return (a, b), pred
    # deg 2
    S = [[sum(x ** (i + j) for x in xs) for j in range(3)] for i in range(3)]
    T = [sum(y * x ** i for x, y in zip(xs, ys)) for i in range(3)]
    # solve 3x3
    import copy
    A = copy.deepcopy(S)
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(A[r][col]))
        A[col], A[piv] = A[piv], A[col]
        T[col], T[piv] = T[piv], T[col]
        for r in range(col + 1, 3):
            f = A[r][col] / A[col][col]
            for c in range(col, 3):
                A[r][c] -= f * A[col][c]
            T[r] -= f * T[col]
    coef = [0.0] * 3
    for r in (2, 1, 0):
        coef[r] = (T[r] - sum(A[r][c] * coef[c] for c in range(r + 1, 3))) / A[r][r]
    pred = [coef[0] + coef[1] * x + coef[2] * x * x for x in xs]
    return tuple(coef), pred


def r2(ys, pred):
    my = sum(ys) / len(ys)
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, pred))
    return 1 - ss_res / ss_tot if ss_tot else 1.0


path = sorted((ROOT / "results").glob("tails_*.jsonl"))[-1]
recs = [json.loads(l) for l in path.read_text().splitlines()]
by = defaultdict(list)
for r in recs:
    if r.get("parsed"):
        by[(r["model"], r["subject"])].append(r)

print(f"{'model':28s} {'subject':16s} {'alpha':>6s} {'linR2':>6s} {'curv':>7s} verdict")
curvs = defaultdict(list)
for (model, subject), rs in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    # median survival per k across samples
    ks = rs[0]["ks"]
    med = {k: statistics.median(float(str(r["parsed"][str(k)]).rstrip("% ")) for r in rs)
           for k in ks}
    pts = [(math.log10(k), math.log10(max(p, 0.001) / 100)) for k, p in med.items() if p > 0]
    if len(pts) < 4:
        continue
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    (a, b), pred1 = polyfit(xs, ys, 1)
    coef2, pred2 = polyfit(xs, ys, 2)
    lin_r2 = r2(ys, pred1)
    curv = coef2[2]
    verdict = ("power-law-like" if lin_r2 > 0.98 and abs(curv) < 0.3
               else "thinner (lognormal-ish)" if curv < 0 else "fatter than power law")
    curvs[subject].append(curv)
    print(f"{model.split('/')[1]:28s} {subject:16s} {-b:>6.2f} {lin_r2:>6.3f} {curv:>7.2f} {verdict}")

print("\nmedian curvature by subject (0 = power law, negative = thinner):")
for s, v in curvs.items():
    print(f"  {s:16s} {statistics.median(v):+.2f}  (n={len(v)})")
print("\nunparsed:", sum(1 for r in recs if not r.get("parsed")), "of", len(recs))
