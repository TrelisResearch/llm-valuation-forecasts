# X thread — copy-paste

Assets (in `assets/`): attach per tweet as noted.

---

## Tweet 1 — attach: headline_reveal.mp4 (or headline_light.png)

What does AI think AI companies are worth?

I asked 26 AI models — knowledge cutoffs from Sept 2021 to Feb 2026, no internet access — what OpenAI, Anthropic, NVIDIA, Google & Meta would be worth every Jan 1 through 2030.

Blue = model forecasts by vintage (darker = later cutoff). Red = what actually happened.

---

## Tweet 2 — attach: growth_rates.png

For public companies, the models appear not to extrapolate the hype - and so real valuations have outpaced model median predictions.

For private companies, models appear to price in momentum, and predict faster growth rates than what I think textbook economics should allow.

• Public companies: ~8–10%/yr - the required rate of return (anything predictable is already in the price)
• Startups: venture rates, ~25–35%/yr

Reality: NVIDIA +78%/yr, OpenAI +150%/yr, Anthropic +387%/yr.

Interestingly, and I don't have a great explanation:

1. Predicted private company growth rates fall to the public 8-10% range if you provide a current company valuation to the model. [It's conceivable that models without this are marking up the fact that private market valuations will always be somewhat out of date at the model cut off, but this should be a one-off lift, not an increased slope in valuations].

2. The LLMs do predict reasonable power law valuation distributions for private companies, and more log normal for public companies. So, the textbook distribution is present, but the models deviate when asked for growth without a grounding current valuation. [We checked whether "point estimate" vs "median" phrasing explains it - it doesn't: unanchored point estimates match unanchored medians almost exactly. The growth rate a model predicts genuinely depends on what it believes the company is currently worth.]

---

## Tweet 3 — attach: tail_beliefs.png

They even believe the "right" distribution shapes.

Ask P(2030 value > k× today's) and plot it log-log: a straight line = power law.

Anthropic: straight lines, tail exponent α ≈ 1.5 — same as the venture-returns literature.
NVIDIA: curved = lognormal, as a public equity should be.

---

## Tweet 4 — no attachment

On dates that have since happened, reality landed above the models' own 90th-percentile forecasts 69% of the time.

Miscalibration? Not necessarily — it's one correlated draw (one AI boom), and by the models' own power-law tails, outliers are the expected surprise. One world isn't enough to reject the textbook.

Interactive charts + methodology + raw data:
research.trelis.com/llm-valuation-forecasts

---

## Single-tweet alternative — attach: growth_rates.png

AI models forecast company valuations like a finance textbook — required-return growth, power-law tails and all. Then the AI boom landed in their own tail: reality beat their 90th percentiles 7 times out of 10. Outlier or miscalibration? One world can't say.
research.trelis.com/llm-valuation-forecasts
