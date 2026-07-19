/* Charts are hand-rolled SVG. Color roles come from CSS custom properties so
   light/dark stay in sync with the stylesheet. */
"use strict";

const NS = "http://www.w3.org/2000/svg";
const tooltip = document.getElementById("tooltip");
let DATA = null, PROBE = null, CALIB = null, TAILS = null;
let state = { company: "OpenAI", evoCompany: "OpenAI", evoTarget: "2030-01-01",
              distQuestion: "named-anthropic" };

const FAMILY_LABELS = {
  "openai-gpt": "OpenAI GPT", "openai-o": "OpenAI o-series",
  "anthropic-claude": "Anthropic Claude", "google-gemini": "Google Gemini",
  "meta-llama": "Meta Llama", "x-ai": "xAI Grok",
};
// fixed categorical slot order — never re-assigned when filters change
const FAMILY_ORDER = ["openai-gpt", "openai-o", "anthropic-claude",
                      "google-gemini", "meta-llama", "x-ai"];

const css = (name) =>
  getComputedStyle(document.querySelector(".viz-root")).getPropertyValue(name).trim();
const cohortColor = (year) => css(`--cohort-${year}`);
const familyColor = (fam) => css(`--fam-${FAMILY_ORDER.indexOf(fam) + 1}`);

const yearFrac = (iso) => {
  const [y, m] = iso.split("-").map(Number);
  return y + (m - 1) / 12;
};
const fmtB = (v) => v >= 1000 ? `$${+(v / 1000).toFixed(v >= 10000 ? 0 : 1)}T`
                              : `$${+v.toFixed(v < 10 ? 1 : 0)}B`;

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

function showTip(html, evt) {
  tooltip.innerHTML = html;
  tooltip.style.display = "block";
  const pad = 14, w = tooltip.offsetWidth, h = tooltip.offsetHeight;
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + w > innerWidth - 8) x = evt.clientX - w - pad;
  if (y + h > innerHeight - 8) y = evt.clientY - h - pad;
  tooltip.style.left = x + "px"; tooltip.style.top = y + "px";
}
const hideTip = () => { tooltip.style.display = "none"; };

/* Generic log-y line chart. series: [{label,color,width,dots,direct,points:[{x,y,meta}]}] */
function lineChart(container, series, opts) {
  container.innerHTML = "";
  const W = opts.width || 560, H = opts.height || 300;
  const m = { t: 12, r: opts.rightPad || 14, b: 26, l: 44 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
                          "aria-label": opts.ariaLabel || "line chart" }, container);
  svg.style.width = "100%"; svg.style.height = "auto"; svg.style.display = "block";

  const xs = series.flatMap(s => s.points.map(p => p.x));
  const ys = series.flatMap(s => s.points.map(p => p.y)).filter(v => v > 0);
  const xDom = opts.xDomain || [Math.min(...xs), Math.max(...xs)];
  let yLo = Math.min(...ys), yHi = Math.max(...ys);
  yLo = Math.pow(10, Math.floor(Math.log10(yLo)));
  yHi = Math.pow(10, Math.ceil(Math.log10(yHi)));
  const X = (v) => m.l + (v - xDom[0]) / (xDom[1] - xDom[0]) * (W - m.l - m.r);
  const Y = (v) => m.t + (1 - (Math.log10(v) - Math.log10(yLo)) /
                   (Math.log10(yHi) - Math.log10(yLo))) * (H - m.t - m.b);

  // grid + y ticks (1-3-10 steps on the log scale)
  const yTicks = [];
  for (let d = Math.log10(yLo); d <= Math.log10(yHi); d++)
    for (const mult of [1, 3]) {
      const v = mult * Math.pow(10, d);
      if (v >= yLo && v <= yHi) yTicks.push(v);
    }
  const yFmt = opts.yFmt || fmtB;
  for (const v of yTicks) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v),
                 stroke: css("--grid"), "stroke-width": 1 }, svg);
    el("text", { x: m.l - 6, y: Y(v) + 3, "text-anchor": "end", "font-size": 9.5,
                 fill: css("--muted") }, svg).textContent = yFmt(v);
  }
  const xTicks = opts.xTicks || [];
  for (const t of xTicks) {
    el("text", { x: X(t.x), y: H - 8, "text-anchor": "middle", "font-size": 9.5,
                 fill: css("--muted") }, svg).textContent = t.label;
  }
  el("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b,
               stroke: css("--axis"), "stroke-width": 1 }, svg);

  for (const s of series) {
    const pts = s.points.filter(p => p.y > 0).sort((a, b) => a.x - b.x);
    if (!pts.length) continue;
    const d = pts.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
    if (pts.length > 1)
      el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 2,
                   "stroke-linecap": "round", "stroke-linejoin": "round",
                   "stroke-dasharray": s.dash || "none" }, svg);
    if (s.dots)
      for (const p of pts)
        el("circle", { cx: X(p.x), cy: Y(p.y), r: 3.4, fill: s.color,
                       stroke: css("--surface-1"), "stroke-width": 2 }, svg);
    if (s.direct) {
      const last = pts[pts.length - 1];
      el("text", { x: X(last.x) + 5, y: Y(last.y) + 3, "font-size": 9.5,
                   "font-weight": 600, fill: s.color }, svg).textContent = s.direct;
    }
  }

  // hover layer: crosshair + nearest-point tooltip
  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: css("--axis"),
                             "stroke-width": 1, "stroke-dasharray": "3,3",
                             visibility: "hidden" }, svg);
  const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b,
                           fill: "transparent" }, svg);
  hit.addEventListener("mousemove", (evt) => {
    const box = svg.getBoundingClientRect();
    const px = (evt.clientX - box.left) * (W / box.width);
    const py = (evt.clientY - box.top) * (H / box.height);
    let best = null, bestD = 1e9;
    for (const s of series)
      for (const p of s.points) {
        if (p.y <= 0) continue;
        const dx = X(p.x) - px, dy = Y(p.y) - py, d2 = dx * dx + dy * dy * 0.35;
        if (d2 < bestD) { bestD = d2; best = { s, p }; }
      }
    if (!best) return;
    cross.setAttribute("x1", X(best.p.x)); cross.setAttribute("x2", X(best.p.x));
    cross.setAttribute("visibility", "visible");
    showTip(best.p.tip || `<div class="t-head">${best.s.label}</div>${fmtB(best.p.y)}`, evt);
  });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
}

/* ---------- headline: small-multiple cohort fans ---------- */
function renderHeadline() {
  const panels = document.getElementById("headline-panels");
  panels.innerHTML = "";
  const legend = document.getElementById("headline-legend");
  const cohortYears = [...new Set(DATA.cohorts.map(c => c.cohort))].sort();
  legend.innerHTML = cohortYears.map(y =>
    `<span class="item"><span class="swatch" style="background:${cohortColor(y)}"></span>cutoff ${y}</span>`
  ).join("") +
  `<span class="item"><span class="swatch dot" style="background:${css("--actual")}"></span>actual</span>`;

  const xTicks = [2024, 2026, 2028, 2030].map(y => ({ x: y, label: String(y) }));
  for (const company of DATA.companies) {
    const div = document.createElement("div");
    div.className = "panel";
    div.innerHTML = `<h3>${company}</h3>`;
    panels.appendChild(div);
    const chart = document.createElement("div");
    div.appendChild(chart);

    const series = cohortYears.map(y => ({
      label: `cutoff ${y}`, color: cohortColor(y), width: 2,
      points: DATA.cohorts.filter(c => c.company === company && c.cohort === y)
        .map(c => ({ x: yearFrac(c.target), y: c.median,
          tip: `<div class="t-head">${company} — Jan ${c.target.slice(0, 4)}</div>
                <div>${fmtB(c.median)}</div>
                <div class="t-sub">median of ${c.n_models} model(s), cutoff ${y}</div>` })),
    }));
    const gt = DATA.ground_truth[company] || {};
    const actualPts = Object.entries(gt)
      .filter(([k, v]) => typeof v === "number" && k !== "latest")
      .map(([k, v]) => ({ x: yearFrac(k), y: v,
        tip: `<div class="t-head">${company} — actual</div><div>${fmtB(v)} (Jan ${k.slice(0, 4)})</div>` }));
    if (typeof gt.latest === "number")
      actualPts.push({ x: yearFrac(DATA.ground_truth.as_of || "2026-07-01"), y: gt.latest,
        tip: `<div class="t-head">${company} — actual</div><div>${fmtB(gt.latest)} (latest)</div>` });
    series.push({ label: "actual", color: css("--actual"), width: 2.5, dots: true,
                  direct: "actual", points: actualPts });

    lineChart(chart, series, { width: 230, height: 210, xTicks, rightPad: 40,
      xDomain: [2023.8, 2030.2], ariaLabel: `${company} forecasts by cutoff vintage` });
  }
}

/* ---------- explorer: per-model lines for one company ---------- */
function segButtons(containerId, values, current, onPick, labelFn) {
  const seg = document.getElementById(containerId);
  seg.innerHTML = "";
  for (const v of values) {
    const b = document.createElement("button");
    b.textContent = labelFn ? labelFn(v) : v;
    b.setAttribute("aria-pressed", String(v === current));
    b.addEventListener("click", () => onPick(v));
    seg.appendChild(b);
  }
}

function renderExplorer() {
  segButtons("company-seg", DATA.companies, state.company,
    (v) => { state.company = v; renderExplorer(); });
  const fams = FAMILY_ORDER.filter(f => DATA.models.some(m => m.family === f));
  document.getElementById("explorer-legend").innerHTML = fams.map(f =>
    `<span class="item"><span class="swatch" style="background:${familyColor(f)}"></span>${FAMILY_LABELS[f]}</span>`
  ).join("");

  const series = DATA.models.map(mdl => ({
    label: mdl.id, color: familyColor(mdl.family), width: 1.6,
    points: DATA.points.filter(p => p.company === state.company && p.model === mdl.id)
      .map(p => ({ x: yearFrac(p.target), y: p.median,
        tip: `<div class="t-head">${mdl.id.split("/")[1]}</div>
              <div>${state.company}, Jan ${p.target.slice(0, 4)}: <b>${fmtB(p.median)}</b></div>
              <div class="t-sub">samples ${fmtB(p.min)}–${fmtB(p.max)} (n=${p.n}) · cutoff ${p.cutoff}</div>` })),
  })).filter(s => s.points.length);
  const gt = DATA.ground_truth[state.company] || {};
  const actualPts = Object.entries(gt)
    .filter(([k, v]) => typeof v === "number" && k !== "latest")
    .map(([k, v]) => ({ x: yearFrac(k), y: v,
      tip: `<div class="t-head">actual</div><div>${fmtB(v)} (Jan ${k.slice(0, 4)})</div>` }));
  series.push({ label: "actual", color: css("--actual"), width: 3, dots: true,
                direct: "actual", points: actualPts });

  lineChart(document.getElementById("explorer-chart"), series, {
    width: 1080, height: 420, rightPad: 56,
    xTicks: [2024, 2025, 2026, 2027, 2028, 2029, 2030].map(y => ({ x: y, label: String(y) })),
    xDomain: [2023.8, 2030.2], ariaLabel: `per-model forecasts for ${state.company}`,
  });
}

/* ---------- evolution: forecast for a fixed target vs cutoff date ---------- */
function renderEvolution() {
  segButtons("evo-company-seg", DATA.companies, state.evoCompany,
    (v) => { state.evoCompany = v; renderEvolution(); });
  segButtons("evo-target-seg", DATA.targets, state.evoTarget,
    (v) => { state.evoTarget = v; renderEvolution(); }, (v) => "Jan " + v.slice(0, 4));

  const pts = DATA.points.filter(p =>
    p.company === state.evoCompany && p.target === state.evoTarget);
  const dotSeries = FAMILY_ORDER.filter(f => pts.some(p => p.family === f)).map(f => ({
    label: FAMILY_LABELS[f], color: familyColor(f), dots: true, width: 0,
    points: pts.filter(p => p.family === f).map(p => ({
      x: yearFrac(p.cutoff + "-01"), y: p.median,
      tip: `<div class="t-head">${p.model.split("/")[1]}</div>
            <div>forecast for Jan ${state.evoTarget.slice(0, 4)}: <b>${fmtB(p.median)}</b></div>
            <div class="t-sub">cutoff ${p.cutoff} · ${FAMILY_LABELS[f]}</div>` })),
  }));
  // cohort medians as connective tissue
  const byYear = {};
  for (const p of pts) (byYear[p.cutoff.slice(0, 4)] ||= []).push(p.median);
  const medPts = Object.entries(byYear).sort().map(([y, vals]) => {
    vals.sort((a, b) => a - b);
    const med = vals.length % 2 ? vals[(vals.length - 1) / 2]
      : (vals[vals.length / 2 - 1] + vals[vals.length / 2]) / 2;
    return { x: +y + 0.5, y: med,
      tip: `<div class="t-head">cohort ${y} median</div><div>${fmtB(med)}</div>` };
  });
  const series = [
    { label: "cohort median", color: css("--muted"), width: 2, dash: "5,4", points: medPts },
    ...dotSeries,
  ];
  const gt = DATA.ground_truth[state.evoCompany] || {};
  const actual = gt[state.evoTarget];
  if (typeof actual === "number")
    series.push({ label: "actual", color: css("--actual"), width: 2, dash: "2,3",
      direct: "actual " + fmtB(actual),
      points: [{ x: 2021.5, y: actual, tip: `actual: ${fmtB(actual)}` },
               { x: 2026.4, y: actual, tip: `actual: ${fmtB(actual)}` }] });

  lineChart(document.getElementById("evolution-chart"), series, {
    width: 1080, height: 380, rightPad: 90,
    xTicks: [2022, 2023, 2024, 2025, 2026].map(y => ({ x: y, label: String(y) })),
    xDomain: [2021.3, 2026.6],
    ariaLabel: `forecast evolution for ${state.evoCompany} target ${state.evoTarget}`,
  });
}

/* ---------- growth: implied CAGR dot plot vs realized ---------- */
function impliedCagr(company, cohort) {
  const pts = DATA.cohorts.filter(c => c.company === company && c.cohort === cohort)
    .map(c => [Number(c.target.slice(0, 4)), Math.log(c.median)]);
  if (pts.length < 2) return null;
  const mx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const my = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  const slope = pts.reduce((s, p) => s + (p[0] - mx) * (p[1] - my), 0) /
                pts.reduce((s, p) => s + (p[0] - mx) ** 2, 0);
  return Math.exp(slope) - 1;
}

function renderGrowth() {
  const companies = ["NVIDIA", "Alphabet (Google)", "Meta Platforms", "OpenAI", "Anthropic"];
  const cohortYears = [...new Set(DATA.cohorts.map(c => c.cohort))].sort();
  const blue = css("--cohort-2024"), red = css("--actual");
  document.getElementById("growth-legend").innerHTML =
    `<span class="item"><span class="swatch dot" style="background:${blue}"></span>model-implied growth (median &amp; range across vintages)</span>
     <span class="item"><span class="swatch dot" style="background:${red}"></span>realized, Jan 2024 → Jul 2026</span>`;

  const W = 1080, rowH = 52, m = { l: 110, r: 30, t: 34, b: 40 };
  const H = companies.length * rowH + m.t + m.b;
  const svg = distSvg(document.getElementById("growth-chart"), W, H,
                      "implied annual growth vs realized, per company");
  const X = (rate) => {  // log scale over 4%..500%
    const lo = Math.log(0.04), hi = Math.log(5);
    return m.l + (Math.log(Math.max(rate, 0.04)) - lo) / (hi - lo) * (W - m.l - m.r);
  };
  // theory bands
  const band = (a, b, label) => {
    el("rect", { x: X(a), y: m.t, width: X(b) - X(a), height: H - m.t - m.b,
                 fill: css("--grid"), opacity: 0.5 }, svg);
    el("text", { x: (X(a) + X(b)) / 2, y: m.t - 8, "text-anchor": "middle",
                 "font-size": 9.5, fill: css("--muted") }, svg).textContent = label;
  };
  band(0.07, 0.10, "public equity required return");
  band(0.15, 0.30, "venture hurdle rates");
  for (const t of [0.05, 0.1, 0.25, 0.5, 1, 2, 4]) {
    el("line", { x1: X(t), x2: X(t), y1: m.t, y2: H - m.b, stroke: css("--grid"),
                 "stroke-width": 1 }, svg);
    el("text", { x: X(t), y: H - m.b + 16, "text-anchor": "middle", "font-size": 10,
                 fill: css("--muted") }, svg).textContent = Math.round(t * 100) + "%";
  }
  companies.forEach((c, i) => {
    const y = m.t + (i + 0.5) * rowH;
    const rates = cohortYears.map(yr => impliedCagr(c, yr)).filter(v => v != null)
      .sort((a, b) => a - b);
    const gt = DATA.ground_truth[c];
    const realized = Math.pow(gt.latest / gt["2024-01-01"], 1 / 2.5) - 1;
    const med = rates[Math.floor(rates.length / 2)];
    el("text", { x: m.l - 12, y: y + 4, "text-anchor": "end", "font-size": 12,
                 fill: css("--text-primary"), "font-weight": 600 }, svg)
      .textContent = { "Alphabet (Google)": "Alphabet", "Meta Platforms": "Meta" }[c] || c;
    el("line", { x1: X(rates[0]), x2: X(rates[rates.length - 1]), y1: y, y2: y,
                 stroke: blue, "stroke-width": 4, opacity: 0.4,
                 "stroke-linecap": "round" }, svg);
    el("line", { x1: X(rates[rates.length - 1]) + 8, x2: X(realized) - 10, y1: y, y2: y,
                 stroke: css("--muted"), "stroke-width": 1.2,
                 "stroke-dasharray": "3,3" }, svg);
    const dot = (x, color, tip) => {
      const g = el("circle", { cx: x, cy: y, r: 6.5, fill: color,
                               stroke: css("--surface-1"), "stroke-width": 2 }, svg);
      g.addEventListener("mousemove", (evt) => showTip(tip, evt));
      g.addEventListener("mouseleave", hideTip);
    };
    dot(X(med), blue, `<div class="t-head">${c} — model forecasts</div>
      median ${Math.round(med * 100)}%/yr (vintages span ${Math.round(rates[0] * 100)}–${Math.round(rates[rates.length - 1] * 100)}%)`);
    dot(X(realized), red, `<div class="t-head">${c} — realized</div>
      ${Math.round(realized * 100)}%/yr, Jan 2024 → Jul 2026`);
  });
}

/* ---------- tails: log-log survival curves ---------- */
function renderTails() {
  const subjects = Object.keys(TAILS.subjects);
  state.tailsSubject ??= "named-anthropic";
  segButtons("tails-subject-seg", subjects, state.tailsSubject,
    (v) => { state.tailsSubject = v; renderTails(); },
    (v) => TAILS.subjects[v].label);
  const s = TAILS.subjects[state.tailsSubject];
  const models = Object.keys(s.models).sort();
  const series = models.map((mid, i) => ({
    label: mid.split("/")[1], color: css("--cohort-2024"),
    width: 1.8, dots: true, direct: mid.split("/")[1],
    points: s.ks.map(k => ({ x: Math.log10(k), y: Number(s.models[mid][String(k)]),
      tip: `<div class="t-head">${mid.split("/")[1]}</div>
            P(2030 value &gt; ${k}× today) = ${s.models[mid][String(k)]}%` }))
      .filter(p => p.y > 0),
  }));
  // shade by index on the ordinal blue ramp for distinguishability
  const ramp = ["--cohort-2021", "--cohort-2023", "--cohort-2024", "--cohort-2025",
                "--cohort-2026", "--fam-5"];
  series.forEach((sr, i) => { sr.color = css(ramp[i % ramp.length]); });

  lineChart(document.getElementById("tails-chart"), series, {
    width: 1080, height: 400, rightPad: 110,
    xTicks: s.ks.map(k => ({ x: Math.log10(k), label: k + "×" })),
    xDomain: [Math.log10(s.ks[0]) - 0.06, Math.log10(s.ks[s.ks.length - 1]) + 0.3],
    ariaLabel: `survival probabilities for ${s.label}`,
    yFmt: (v) => (v >= 1 ? v : v.toFixed(v >= 0.1 ? 1 : 2)) + "%",
  });
}

/* ---------- distributions: p10-p90 intervals + P(below) bars ---------- */
function distSvg(container, W, H, ariaLabel) {
  container.innerHTML = "";
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": ariaLabel },
                 container);
  svg.style.width = "100%"; svg.style.height = "auto"; svg.style.display = "block";
  return svg;
}

function renderDistributions() {
  const qKeys = Object.keys(PROBE.labels);
  segButtons("dist-question-seg", qKeys, state.distQuestion,
    (v) => { state.distQuestion = v; renderDistributions(); },
    (v) => PROBE.labels[v]);
  const rows = PROBE.rows.filter(r => r.question === state.distQuestion)
    .sort((a, b) => a.cutoff < b.cutoff ? -1 : 1);
  const anchor = PROBE.anchors[state.distQuestion];
  const blue = css("--cohort-2024"), green = css("--fam-2");

  document.getElementById("dist-legend").innerHTML =
    `<span class="item"><span class="swatch" style="background:${blue};height:8px;width:3px"></span>10th–90th percentile</span>
     <span class="item"><span class="swatch dot" style="background:${blue}"></span>median (p50)</span>
     <span class="item"><span class="swatch dot" style="background:${green}"></span>point estimate (main run)</span>
     <span class="item"><span class="swatch" style="background:${css("--muted")}"></span>current valuation</span>`;

  // interval chart: x = model (categorical), y = log USD B
  const W = 1080, H = 360, m = { t: 16, r: 20, b: 54, l: 52 };
  const svg = distSvg(document.getElementById("dist-chart"), W, H,
                      `2030 distribution per model, ${PROBE.labels[state.distQuestion]}`);
  const vals = rows.flatMap(r => [r.p10, r.p90, r.point_estimate || anchor, anchor]).filter(Boolean);
  const yLo = Math.pow(10, Math.floor(Math.log10(Math.min(...vals))));
  const yHi = Math.pow(10, Math.ceil(Math.log10(Math.max(...vals))));
  const Y = (v) => m.t + (1 - (Math.log10(v) - Math.log10(yLo)) /
                   (Math.log10(yHi) - Math.log10(yLo))) * (H - m.t - m.b);
  const X = (i) => m.l + (i + 0.5) * (W - m.l - m.r) / rows.length;

  for (let d = Math.log10(yLo); d <= Math.log10(yHi); d++) {
    const v = Math.pow(10, d);
    el("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: css("--grid"),
                 "stroke-width": 1 }, svg);
    el("text", { x: m.l - 6, y: Y(v) + 3, "text-anchor": "end", "font-size": 10,
                 fill: css("--muted") }, svg).textContent = fmtB(v);
  }
  el("line", { x1: m.l, x2: W - m.r, y1: Y(anchor), y2: Y(anchor), stroke: css("--muted"),
               "stroke-width": 1.5, "stroke-dasharray": "5,4" }, svg);
  el("text", { x: W - m.r, y: Y(anchor) - 5, "text-anchor": "end", "font-size": 10,
               fill: css("--muted") }, svg).textContent = `today ${fmtB(anchor)}`;

  rows.forEach((r, i) => {
    const x = X(i);
    const tip = `<div class="t-head">${r.model.split("/")[1]}</div>
      <div>p10 ${fmtB(r.p10)} · p50 ${fmtB(r.p50)} · p90 ${fmtB(r.p90)}</div>
      ${r.point_estimate ? `<div>point estimate: ${fmtB(r.point_estimate)}</div>` : ""}
      <div class="t-sub">P(below today): ${r.p_below}% · cutoff ${r.cutoff} · n=${r.n}</div>`;
    const g = el("g", {}, svg);
    el("line", { x1: x, x2: x, y1: Y(r.p10), y2: Y(r.p90), stroke: blue,
                 "stroke-width": 3, "stroke-linecap": "round" }, g);
    el("circle", { cx: x, cy: Y(r.p50), r: 5.5, fill: blue,
                   stroke: css("--surface-1"), "stroke-width": 2 }, g);
    if (r.point_estimate)
      el("circle", { cx: x + 14, cy: Y(r.point_estimate), r: 5.5, fill: green,
                     stroke: css("--surface-1"), "stroke-width": 2 }, g);
    el("text", { x, y: H - m.b + 16, "text-anchor": "middle", "font-size": 10,
                 fill: css("--text-secondary") }, g).textContent = r.model.split("/")[1];
    el("text", { x, y: H - m.b + 30, "text-anchor": "middle", "font-size": 9,
                 fill: css("--muted") }, g).textContent = `cutoff ${r.cutoff}`;
    const hit = el("rect", { x: x - 24, y: m.t, width: 62, height: H - m.t - m.b,
                             fill: "transparent" }, g);
    hit.addEventListener("mousemove", (evt) => showTip(tip, evt));
    hit.addEventListener("mouseleave", hideTip);
  });

  // P(below) bars
  const H2 = 240, m2 = { t: 14, r: 20, b: 54, l: 52 };
  const svg2 = distSvg(document.getElementById("pbelow-chart"), W, H2,
                       `probability below current valuation, ${PROBE.labels[state.distQuestion]}`);
  const Y2 = (v) => m2.t + (1 - v / 100) * (H2 - m2.t - m2.b);
  el("rect", { x: m2.l, y: Y2(45), width: W - m2.l - m2.r, height: Y2(35) - Y2(45),
               fill: css("--grid"), opacity: 0.55 }, svg2);
  el("text", { x: W - m2.r, y: Y2(45) - 4, "text-anchor": "end", "font-size": 9.5,
               fill: css("--muted") }, svg2).textContent = "≈ fair-price range (35–45%)";
  for (const v of [0, 25, 50, 75, 100]) {
    el("line", { x1: m2.l, x2: W - m2.r, y1: Y2(v), y2: Y2(v), stroke: css("--grid"),
                 "stroke-width": 1 }, svg2);
    el("text", { x: m2.l - 6, y: Y2(v) + 3, "text-anchor": "end", "font-size": 10,
                 fill: css("--muted") }, svg2).textContent = v + "%";
  }
  const bw = Math.min(44, (W - m2.l - m2.r) / rows.length - 18);
  rows.forEach((r, i) => {
    const x = X(i);
    el("rect", { x: x - bw / 2, y: Y2(r.p_below), width: bw, height: Y2(0) - Y2(r.p_below),
                 rx: 4, fill: blue }, svg2);
    el("text", { x, y: Y2(r.p_below) - 6, "text-anchor": "middle", "font-size": 10.5,
                 "font-weight": 600, fill: css("--text-secondary") }, svg2)
      .textContent = r.p_below + "%";
    el("text", { x, y: H2 - m2.b + 16, "text-anchor": "middle", "font-size": 10,
                 fill: css("--text-secondary") }, svg2).textContent = r.model.split("/")[1];
  });
}

/* ---------- calibration: stacked bucket bars ---------- */
function renderCalibration() {
  const BUCKETS = ["below p10", "p10-p50", "p50-p90", "above p90"];
  const colors = [css("--cohort-2021"), css("--cohort-2023"), css("--cohort-2025"),
                  css("--actual")];
  document.getElementById("calib-legend").innerHTML = BUCKETS.map((b, i) =>
    `<span class="item"><span class="swatch" style="background:${colors[i]};height:10px;width:14px;border-radius:3px"></span>${b}</span>`
  ).join("");

  const rows = [
    ["Perfectly calibrated (reference)", CALIB.perfect],
    ["All models pooled", CALIB.overall],
    ["Private (OpenAI, Anthropic)", CALIB.by_kind.private],
    ["Public (NVDA, GOOGL, META)", CALIB.by_kind.public],
    ...Object.entries(CALIB.by_model).map(([m, s]) => [m.split("/")[1], s]),
  ];
  const W = 1080, rowH = 34, m = { l: 250, r: 56, t: 6 };
  const H = rows.length * rowH + m.t + 6;
  const svg = distSvg(document.getElementById("calib-chart"), W, H,
                      "calibration bucket shares per model");
  rows.forEach(([label, s], ri) => {
    const y = m.t + ri * rowH;
    el("text", { x: m.l - 10, y: y + 19, "text-anchor": "end", "font-size": 11,
                 fill: css("--text-secondary"),
                 "font-style": ri === 0 ? "italic" : "normal" }, svg).textContent = label;
    let x = m.l;
    BUCKETS.forEach((b, bi) => {
      const w = (s[b] || 0) * (W - m.l - m.r);
      if (w <= 0) { return; }
      el("rect", { x, y: y + 5, width: Math.max(w - 2, 1), height: 20, rx: 3,
                   fill: colors[bi], opacity: ri === 0 ? 0.45 : 1 }, svg);
      if ((s[b] || 0) >= 0.08)
        el("text", { x: x + w / 2, y: y + 19, "text-anchor": "middle", "font-size": 10,
                     "font-weight": 600,
                     fill: bi >= 2 ? "#fff" : css("--text-primary") }, svg)
          .textContent = Math.round(s[b] * 100) + "%";
      x += w;
    });
    if (s.n)
      el("text", { x: W - m.r + 8, y: y + 19, "font-size": 10, fill: css("--muted") },
         svg).textContent = "n=" + s.n;
  });
}

/* ---------- table + method ---------- */
function renderTable() {
  const t = document.getElementById("data-table");
  const years = DATA.targets.map(d => d.slice(0, 4));
  const cohortYears = [...new Set(DATA.cohorts.map(c => c.cohort))].sort();
  let html = `<tr><th>Company</th><th>Cutoff cohort</th>${years.map(y => `<th>Jan ${y}</th>`).join("")}</tr>`;
  for (const company of DATA.companies)
    for (const y of cohortYears) {
      const cells = DATA.targets.map(tg => {
        const row = DATA.cohorts.find(c => c.company === company && c.cohort === y && c.target === tg);
        return `<td>${row ? fmtB(row.median) : "–"}</td>`;
      });
      if (DATA.cohorts.some(c => c.company === company && c.cohort === y))
        html += `<tr><td>${company}</td><td>${y}</td>${cells.join("")}</tr>`;
    }
  t.innerHTML = html;
}

function renderMethod() {
  document.getElementById("method").innerHTML =
    `<b>Method.</b> ${DATA.models.length} models served via OpenRouter, knowledge cutoffs
    Sep 2021 → Feb 2026 (provider-documented). Each (model, company, date) asked in a
    separate conversation with no internet access and no revealed current date; reasoning
    models run at standard thinking effort. 3 samples per question; lines show medians.
    Private-company questions ask post-money valuation; public-company questions ask market
    capitalization (split-invariant). Targets at or before a model's cutoff month are excluded.
    Models that refused once were nudged once in-conversation. Actual values: funding rounds /
    tenders (OpenAI, Anthropic) and year-end market caps (NVDA, GOOGL, META), as of
    ${DATA.ground_truth.as_of || "2026-07"}. Distribution probe: 5 models, 2 samples per
    question, percentiles anchored on stated current valuations. Runs: ${DATA.run}, ${PROBE.run}.
    Code + raw data: <a href="https://github.com/TrelisResearch/llm-valuation-forecasts">TrelisResearch/llm-valuation-forecasts</a>
    · by <a href="https://x.com/ronankmcgovern">@ronankmcgovern</a>.`;
}

function renderAll() {
  renderHeadline(); renderGrowth(); renderTails(); renderDistributions();
  renderCalibration(); renderExplorer(); renderEvolution(); renderTable(); renderMethod();
}

Promise.all([fetch("data.json"), fetch("probe.json"), fetch("calib.json"),
             fetch("tails.json")])
  .then(rs => Promise.all(rs.map(r => r.json())))
  .then(([d, p, c, t]) => {
    DATA = d; PROBE = p; CALIB = c; TAILS = t;
    renderAll();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderAll);
  });
