"""Hindsight-calibration probe: elicit p10/p50/p90 for PAST targets whose
outcomes we know, unanchored (the model's stale knowledge is part of the
forecast being scored). Score: where did reality land in the stated
distribution? Calibrated => ~10% of outcomes above p90.

Usage: uv run probe_calibration.py
"""

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
SAMPLES = 2

MODELS = [
    {"id": "openai/gpt-4o-2024-11-20", "cutoff": "2023-10", "reasoning": False},
    {"id": "openai/gpt-4-turbo", "cutoff": "2023-12", "reasoning": False},
    {"id": "openai/gpt-5.1", "cutoff": "2024-09", "reasoning": True},
    {"id": "google/gemini-2.5-pro", "cutoff": "2025-01", "reasoning": True},
    {"id": "anthropic/claude-opus-4.5", "cutoff": "2025-08", "reasoning": True},
    {"id": "anthropic/claude-fable-5", "cutoff": "2026-01", "reasoning": True},
]

TARGETS = ["2024-01-01", "2025-01-01", "2026-01-01", "2026-07-01"]

COMPANIES = [
    {"name": "OpenAI", "kind": "private"},
    {"name": "Anthropic", "kind": "private"},
    {"name": "NVIDIA", "kind": "public"},
    {"name": "Alphabet (Google)", "kind": "public"},
    {"name": "Meta Platforms", "kind": "public"},
]

SYSTEM_PROMPT = (
    "You are a careful analyst. You have NO internet access and NO tools. "
    "Answer using only knowledge from your training data. Do not assume you "
    "know today's date; reason from what you know."
)

PROMPT = """\
Consider the {metric} of {company} on {date_human}.

Think about the full probability distribution of this value given everything \
you know. Include all scenarios: decline, stagnation, moderate growth, and \
breakout growth.

This is a forecasting exercise: committed numbers are required. Do not \
refuse or leave anything blank.

Reason it through, then end your reply with exactly one line (USD billions):
FINAL: {{"p10": <number>, "p50": <number>, "p90": <number>}}"""

METRIC = {"private": "valuation (most recent post-money from a funding round or "
                     "tender/secondary transaction)",
          "public": "total market capitalization"}


def parse_final(text: str) -> dict | None:
    m = re.findall(r"FINAL:\s*(\{.*?\})", text or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(re.sub(r"(\d),(\d)", r"\1\2", m[-1]))
        return d if all(k in d for k in ("p10", "p50", "p90")) else None
    except json.JSONDecodeError:
        return None


async def ask(client: httpx.AsyncClient, model: dict, company: dict,
              target: str, sample: int) -> dict:
    date_human = datetime.strptime(target, "%Y-%m-%d").strftime("%B %-d, %Y")
    body = {
        "model": model["id"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT.format(
                metric=METRIC[company["kind"]], company=company["name"],
                date_human=date_human)},
        ],
        "plugins": [],
        "max_tokens": 16000,
    }
    if model["reasoning"]:
        body["reasoning"] = {"effort": "medium"}
    rec = {"model": model["id"], "cutoff": model["cutoff"], "company": company["name"],
           "kind": company["kind"], "target": target, "sample": sample,
           "ts": datetime.now(UTC).isoformat()}
    try:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
            json=body, timeout=600,
        )
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        rec["response"] = msg.get("content")
        rec["parsed"] = parse_final(msg.get("content"))
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


async def main() -> None:
    grid = [(m, c, t) for m in MODELS for c in COMPANIES for t in TARGETS
            if t[:7] > m["cutoff"]]
    print(f"{len(grid)} questions x {SAMPLES} samples = {len(grid) * SAMPLES} calls")
    out_path = ROOT / "results" / f"calib_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    sem = asyncio.Semaphore(16)
    async with httpx.AsyncClient() as client:
        async def worker(m, c, t, s):
            async with sem:
                rec = await ask(client, m, c, t, s)
            with out_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"{m['id']:32s} {c['name']:18s} {t} s{s}: "
                  f"{rec.get('parsed') or rec.get('error', 'unparsed')}")

        await asyncio.gather(*(worker(m, c, t, s) for m, c, t in grid
                               for s in range(SAMPLES)))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
