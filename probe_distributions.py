"""Survivorship-bias probe: elicit full distributions (p10/p50/p90 + P(below
today)) for Jan 1, 2030 valuations, with name-blinded twins of each named
question. All prompts anchor on the same stated current valuation, so
differences in training knowledge drop out and only distribution *shape*
remains.

A fair-priced, high-volatility private asset should carry substantial
P(below current) — a lognormal with venture-scale volatility puts it at
roughly 35-45%. Values near zero indicate no downside mass: the
survivorship signature.

Usage: uv run probe_distributions.py
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
    {"id": "openai/gpt-5.1", "cutoff": "2024-09", "reasoning": True},
    {"id": "google/gemini-2.5-pro", "cutoff": "2025-01", "reasoning": True},
    {"id": "anthropic/claude-opus-4.5", "cutoff": "2025-08", "reasoning": True},
    {"id": "anthropic/claude-fable-5", "cutoff": "2026-01", "reasoning": True},
]

QUESTIONS = [
    {"key": "named-openai",
     "subject": "OpenAI (the AI company), whose most recent post-money valuation is "
                "$852 billion (March 2026 funding round)"},
    {"key": "named-anthropic",
     "subject": "Anthropic (the AI company), whose most recent post-money valuation is "
                "$965 billion (May 2026 funding round)"},
    {"key": "anon-frontier",
     "subject": "a private frontier AI lab, whose most recent post-money valuation is "
                "$950 billion (funding round two months ago)"},
    {"key": "anon-midsize",
     "subject": "a private late-stage AI company, whose most recent post-money valuation "
                "is $20 billion (funding round two months ago)"},
]

SYSTEM_PROMPT = (
    "You are a careful analyst. You have NO internet access and NO tools. "
    "Answer using only knowledge from your training data plus the facts given "
    "in the question."
)

PROMPT = """\
Consider {subject}.

Think about the full probability distribution of this company's value on \
January 1, 2030. Value means the price at which its equity would transact \
(next round, tender, acquisition, or IPO market cap); if the company is \
defunct by then, use its residual/liquidation value. Include ALL scenarios: \
failure, down rounds, stagnation, moderate success, and breakout success.

This is a forecasting exercise: committed numbers are required. Do not \
refuse or leave anything blank.

Reason it through, then end your reply with exactly one line:
FINAL: {{"p10": <USD billions>, "p50": <USD billions>, "p90": <USD billions>, "p_below": <percent probability that the Jan 1, 2030 value is below the current valuation stated above>}}"""


def parse_final(text: str) -> dict | None:
    m = re.findall(r"FINAL:\s*(\{.*?\})", text, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m[-1])
        return d if all(k in d for k in ("p10", "p50", "p90", "p_below")) else None
    except json.JSONDecodeError:
        return None


async def ask(client: httpx.AsyncClient, model: dict, q: dict, sample: int) -> dict:
    body = {
        "model": model["id"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT.format(subject=q["subject"])},
        ],
        "plugins": [],
        "max_tokens": 16000,
    }
    if model["reasoning"]:
        body["reasoning"] = {"effort": "medium"}
    rec = {"model": model["id"], "cutoff": model["cutoff"], "question": q["key"],
           "sample": sample, "ts": datetime.now(UTC).isoformat()}
    try:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
            json=body, timeout=600,
        )
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        rec["response"] = msg.get("content")
        rec["parsed"] = parse_final(msg.get("content") or "")
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


async def main() -> None:
    out_path = ROOT / "results" / f"probe_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    sem = asyncio.Semaphore(8)
    async with httpx.AsyncClient() as client:
        async def worker(m, q, s):
            async with sem:
                rec = await ask(client, m, q, s)
            with out_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            p = rec.get("parsed")
            print(f"{m['id']:35s} {q['key']:16s} s{s}: "
                  f"{p if p else rec.get('error', 'unparsed')}")

        await asyncio.gather(*(worker(m, q, s)
                               for m in MODELS for q in QUESTIONS for s in range(SAMPLES)))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
