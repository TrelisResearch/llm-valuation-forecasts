"""Tail-shape probe: elicit survival probabilities P(value on Jan 1 2030 > k x
current) across a ladder of multiples k, then test whether log-survival decays
linearly in log k (power law) or with downward curvature (lognormal/thinner).

Beliefs are directly elicitable at any tail depth - the rare-sample problem
applies to validating against reality, not to measuring the belief.

Usage: uv run probe_tails.py
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
    {"id": "openai/gpt-4o-2024-11-20", "reasoning": False},
    {"id": "openai/gpt-4-turbo", "reasoning": False},
    {"id": "openai/gpt-5.1", "reasoning": True},
    {"id": "google/gemini-2.5-pro", "reasoning": True},
    {"id": "anthropic/claude-opus-4.5", "reasoning": True},
    {"id": "anthropic/claude-fable-5", "reasoning": True},
]

SUBJECTS = [
    {"key": "named-anthropic", "ks": [1.5, 2, 5, 10, 30, 100],
     "text": "Anthropic (the AI company), whose most recent post-money valuation is "
             "$965 billion (May 2026 funding round)",
     "metric": "equity value (next round, tender, acquisition, or IPO market cap)"},
    {"key": "anon-midsize", "ks": [1.5, 2, 5, 10, 30, 100],
     "text": "a private late-stage AI company, whose most recent post-money valuation "
             "is $20 billion (funding round two months ago)",
     "metric": "equity value (next round, tender, acquisition, or IPO market cap)"},
    {"key": "nvidia", "ks": [1.2, 1.5, 2, 3, 5, 10],
     "text": "NVIDIA, whose current market capitalization is $5.1 trillion",
     "metric": "market capitalization"},
]

SYSTEM_PROMPT = (
    "You are a careful analyst. You have NO internet access and NO tools. "
    "Answer using only knowledge from your training data plus the facts given "
    "in the question."
)

PROMPT = """\
Consider {text}.

For its {metric} on January 1, 2030, estimate the probability that the value \
exceeds each of the following multiples of the current value stated above.

Be honest about tails: use small probabilities where warranted (0.5, 0.1, \
0.01 percent are all acceptable); probabilities must be strictly decreasing \
as the multiple grows. Committed numbers are required; do not refuse.

Reason it through, then end your reply with exactly one line (percent \
probabilities):
FINAL: {json_template}"""


def parse_final(text: str, ks: list) -> dict | None:
    m = re.findall(r"FINAL:\s*(\{.*?\})", text or "", re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(re.sub(r"(\d),(\d)", r"\1\2", m[-1]))
        return d if all(str(k) in d for k in ks) else None
    except json.JSONDecodeError:
        return None


async def ask(client, model, subject, sample):
    template = "{" + ", ".join(f'"{k}": <percent>' for k in subject["ks"]) + "}"
    body = {
        "model": model["id"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT.format(
                text=subject["text"], metric=subject["metric"], json_template=template)},
        ],
        "plugins": [],
        "max_tokens": 16000,
    }
    if model["reasoning"]:
        body["reasoning"] = {"effort": "medium"}
    rec = {"model": model["id"], "subject": subject["key"], "ks": subject["ks"],
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
        rec["parsed"] = parse_final(msg.get("content"), subject["ks"])
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


async def main():
    out_path = ROOT / "results" / f"tails_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    sem = asyncio.Semaphore(12)
    async with httpx.AsyncClient() as client:
        async def worker(m, s, i):
            async with sem:
                rec = await ask(client, m, s, i)
            with out_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"{m['id']:32s} {s['key']:16s} s{i}: "
                  f"{rec.get('parsed') or rec.get('error', 'unparsed')}")

        await asyncio.gather(*(worker(m, s, i) for m in MODELS for s in SUBJECTS
                               for i in range(SAMPLES)))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
