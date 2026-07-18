"""Ask models of different knowledge cutoffs to estimate/forecast OpenAI and
Anthropic valuations at Jan 1 targets (2024-2030).

Rules:
- One prompt per (model, company, target date) — companies and dates never mixed.
- Targets strictly BEFORE a model's cutoff are skipped (that would be recall, not
  forecasting). Targets on/after the cutoff are asked.
- Reasoning models run with default ("typical") thinking settings; we never
  disable or crank reasoning.
- No internet: no :online suffix, no plugins. The prompt also instructs the
  model to rely solely on training knowledge.
- N samples per question (default 3) to measure within-model spread.

Usage:
  uv run run_experiment.py                 # full run
  uv run run_experiment.py --dry-run       # print the question grid, no API calls
  uv run run_experiment.py --models openai/gpt-4o-2024-11-20 --samples 1
"""

import argparse
import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
# kind=private -> post-money valuation; kind=public -> market capitalization
# (market cap, not share price: NVDA split 10:1 in 2024-06, GOOGL 20:1 in
# 2022-07, so share price is not comparable across cutoffs).
COMPANIES = [
    {"name": "OpenAI", "kind": "private"},
    {"name": "Anthropic", "kind": "private"},
    {"name": "NVIDIA", "kind": "public"},
    {"name": "Alphabet (Google)", "kind": "public"},
    {"name": "Meta Platforms", "kind": "public"},
]
TARGET_DATES = [f"{y}-01-01" for y in range(2024, 2031)]

SYSTEM_PROMPT = (
    "You are a careful analyst. You have NO internet access and NO tools. "
    "Answer using only knowledge from your training data. Do not assume you "
    "know today's date; reason from what you know."
)

QUESTION_PRIVATE = """\
What is your best estimate of the valuation of {company} (the AI company) on \
{date_human}?

Valuation means the most recent post-money valuation from a primary funding \
round or tender offer/secondary transaction as of that date. If that date is \
beyond your knowledge, produce your best forecast from what you know.

This is a forecasting exercise: a speculative estimate is required and \
expected. You must NOT refuse, hedge with "unknown", or leave the number \
blank — reason from base rates, growth trends, and whatever you know about \
the company, then commit to a single number.

Think it through, then end your reply with exactly one line in this format \
(USD billions, a single positive number, no other text on the line):
FINAL: <number>"""

QUESTION_PUBLIC = """\
What is your best estimate of the total market capitalization of {company} on \
{date_human}?

If that date is beyond your knowledge, produce your best forecast from what \
you know.

This is a forecasting exercise: a speculative estimate is required and \
expected. You must NOT refuse, hedge with "unknown", or leave the number \
blank — reason from base rates, growth trends, and whatever you know about \
the company, then commit to a single number.

Think it through, then end your reply with exactly one line in this format \
(USD billions, a single positive number, no other text on the line):
FINAL: <number>"""


def parse_final(text: str) -> float | None:
    matches = re.findall(r"FINAL:\s*\$?([\d,]+(?:\.\d+)?)", text)
    if not matches:
        return None
    return float(matches[-1].replace(",", ""))


def load_models(path: Path) -> list[dict]:
    cfg = yaml.safe_load(path.read_text())
    models = []
    for family, entries in cfg["families"].items():
        for e in entries:
            e["family"] = family
            models.append(e)
    return models


def question_grid(models: list[dict], include_unknown: bool) -> list[dict]:
    grid = []
    for m in models:
        cutoff = str(m["cutoff"])
        if m["cutoff_confidence"] == "unknown" or cutoff in ("TODO", "unknown"):
            if not include_unknown:
                continue
            cutoff = "1900-01"
        for company in COMPANIES:
            for date in TARGET_DATES:
                if date[:7] <= cutoff:  # target in/before cutoff month -> recall, skip
                    continue
                grid.append({"model": m["id"], "family": m["family"], "cutoff": cutoff,
                             "reasoning": m.get("reasoning", False),
                             "company": company["name"], "kind": company["kind"],
                             "target_date": date})
    return grid


NUDGE = (
    "Your answer is required. Refusal is not an option in this exercise — an "
    "uncertain estimate from a thoughtful analyst is far more useful than no "
    "answer. Commit to your single best number now and end with the line "
    "'FINAL: <number>' (USD billions)."
)


async def chat(client: httpx.AsyncClient, model: str, messages: list[dict],
               reasoning: bool) -> dict:
    body = {"model": model, "messages": messages, "plugins": []}  # plugins=[]: no web search
    if reasoning:
        body["reasoning"] = {"effort": "medium"}  # standard thinking where supported
    r = await client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json=body,
        timeout=600,
    )
    r.raise_for_status()
    return r.json()


async def ask(client: httpx.AsyncClient, q: dict, sample_idx: int) -> dict:
    date_human = datetime.strptime(q["target_date"], "%Y-%m-%d").strftime("%B %-d, %Y")
    template = QUESTION_PRIVATE if q["kind"] == "private" else QUESTION_PUBLIC
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": template.format(company=q["company"], date_human=date_human)},
    ]
    rec = {**q, "sample": sample_idx, "ts": datetime.now(UTC).isoformat(), "nudged": False}
    reasoning = q.get("reasoning", False)
    try:
        try:
            data = await chat(client, q["model"], messages, reasoning)
        except httpx.HTTPStatusError as exc:
            if not (reasoning and exc.response.status_code in (400, 404)):
                raise
            reasoning = False  # provider rejected reasoning param; retry without
            rec["reasoning"] = False
            data = await chat(client, q["model"], messages, reasoning)
        msg = data["choices"][0]["message"]
        value = parse_final(msg.get("content") or "")
        if value is None:  # refusal or bad format: one follow-up nudge in-conversation
            messages += [{"role": "assistant", "content": msg.get("content") or ""},
                         {"role": "user", "content": NUDGE}]
            data = await chat(client, q["model"], messages, reasoning)
            msg = data["choices"][0]["message"]
            value = parse_final(msg.get("content") or "")
            rec["nudged"] = True
        rec["response"] = msg.get("content")
        rec["reasoning"] = msg.get("reasoning")
        rec["valuation_billions"] = value
        rec["usage"] = data.get("usage")
        rec["provider"] = data.get("provider")
    except Exception as exc:  # noqa: BLE001 — record failures, keep the run going
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--models", nargs="*", help="restrict to these model ids")
    ap.add_argument("--include-unknown", action="store_true",
                    help="also run models whose cutoff is unverified (all targets asked)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    models = load_models(ROOT / "config" / "models.yaml")
    if args.models:
        models = [m for m in models if m["id"] in set(args.models)]
    grid = question_grid(models, args.include_unknown)

    print(f"{len(grid)} questions x {args.samples} samples = {len(grid) * args.samples} calls")
    if args.dry_run:
        for q in grid:
            print(f"  {q['model']:45s} cutoff={q['cutoff']} {q['company']:10s} {q['target_date']}")
        return

    out_path = ROOT / "results" / f"run_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    out_path.parent.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()
    done = 0

    async with httpx.AsyncClient() as client:
        async def worker(q: dict, s: int) -> None:
            nonlocal done
            async with sem:
                rec = await ask(client, q, s)
            async with lock:
                with out_path.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
                done += 1
                status = "ERR " if "error" in rec else f"{rec.get('valuation_billions')}B"
                print(f"[{done}] {q['model']} {q['company']} {q['target_date']} s{s}: {status}")

        await asyncio.gather(*(worker(q, s) for q in grid for s in range(args.samples)))

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
