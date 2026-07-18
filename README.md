# LLM Valuation Forecasts by Knowledge Cutoff

Ask models from the same families — but with different knowledge cutoffs — to
estimate/forecast the valuation of OpenAI and Anthropic at Jan 1 targets
(2024 through 2030). Because each model's knowledge stops at its cutoff, a
lineage gives a natural panel of "forecasters frozen at different dates".

## Design

- One prompt per (model, company, target date). Companies and dates are never
  mixed in a prompt.
- A target date strictly **before** a model's cutoff is skipped — the model
  would be recalling, not forecasting. Targets on/after the cutoff are asked.
  (Targets between cutoff and the model's release are a useful "hindcast"
  band: forecast for the model, known outcome for us.)
- Reasoning models run at their default/typical thinking settings.
- **No internet access**: no `:online` routing, `plugins: []`, and the system
  prompt forbids assuming today's date.
- N samples per question (default 3) to measure within-model spread; the
  answer is parsed from a `FINAL: <number>` line (USD billions).

## Model lineages

See `config/models.yaml`. Cutoffs marked `TODO` are pending verification —
the runner skips them unless `--include-unknown`. Qwen/DeepSeek generally do
not publish cutoffs; for those we plan to *empirically elicit* the cutoff
(see below) before trusting any documented value.

## Run

```bash
uv run run_experiment.py --dry-run     # inspect the question grid
uv run run_experiment.py               # full run -> results/run_*.jsonl
```

`OPENROUTER_API_KEY` is read from `.env` (not committed).

## Planned improvements

1. **Empirical cutoff probe**: before the main run, ask each model (a) its
   self-reported cutoff and (b) a battery of dated factual questions (funding
   rounds, CEO changes, releases) to bracket the *effective* cutoff, which
   often differs from the documented one (post-training data leaks forward).
2. **Distributional elicitation**: ask for 10th/50th/90th percentiles rather
   than a point estimate, enabling proper scoring (CRPS / interval coverage)
   against realized valuations.
3. **Ground truth table**: actual post-money valuations at each Jan 1 for
   both companies, so hindcast-band answers can be scored.
4. **Controls**: same-cutoff models across families (does family matter
   beyond cutoff?), and a paraphrase-robustness check on the prompt.
