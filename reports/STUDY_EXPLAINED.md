# Tokenized Gold Over the Weekend — Explained Simply

A plain-English walkthrough of the thesis, the test, the math, the data, and what the numbers actually mean (v2.1 / study freeze `2026-11-13`).

Full numbers and charts: [`findings.md`](findings.md) · Published write-up: [`x_article.md`](x_article.md) · Code: project root · Definitions frozen in [`../PREREGISTRATION.md`](../PREREGISTRATION.md)

---

## 1. The thesis (in one paragraph)

Traditional gold markets close **Friday 17:00 ET** and reopen **Sunday 18:00 ET**. Tokenized gold (XAUT, PAXG) — crypto tokens each backed by one troy ounce of vaulted gold — keeps trading on exchanges all weekend. During those hours there is **no mint/redeem window** to force the token price back to the real gold price. So the tokens can drift. The curiosity question is: **when they drift, does real gold “catch up” at the Sunday reopen, does the token snap back, or is there no clear pattern?**

This study is **descriptive**. It is not a trading bot and does not claim a costed edge.

---

## 2. The original research prompt (what we set out to do)

We built a sibling of the BTC Fear & Greed study with this brief:

> Gold is closed Fri 17:00 → Sun 18:00 ET. Tokenized gold keeps trading. Using all weekends from **Jan 2025 → 2026-11-13** (study freeze), answer:
>
> 1. How far do the tokens drift from gold over the weekend?
> 2. When tokens move over the weekend, does gold follow at the Sunday reopen?
> 3. Who closes the gap — gold catching up, or the token snapping back?
> 4. Is it different on news / quiet / crypto-crash weekends?
> 5. What were the biggest weekend dislocations, and what happened next?
>
> Every answer should be a number + a chart, in plain English. Free data only. No trading rules. Try hard **not** to overclaim.

We also set up (but did not run) a later strategy phase: a reusable weekend table, a study freeze date, and a live order-book recorder so future costed tests do not contaminate these descriptive results.

---

## 3. How we tested it

Think of each weekend as one experiment.

```
Friday 17:00 ET          Weekend (gold closed)         Sunday 18:00 ET
     │                                                      │
     │  Token keeps trading on crypto venues                │  Gold reopens
     │  (no mint/redeem anchor)                             │
     ▼                                                      ▼
  Measure Friday           Measure how far the           Measure gold’s
  gold + token prices      token moved by                reopen “gap”
                           5 min before reopen           (+15 minutes)
```

**Steps we actually ran:**

1. **Download** 1-minute prices for gold (Dukascopy XAU/USD) and tokens (Binance via `data-api.binance.vision` only; OKX; Bybit/Kraken where available).
2. **Convert** USDT prices to USD with full-history Bitstamp rates.
3. **Build a weekend table** — one row per weekend × token × venue (`data/processed/weekends.parquet`). Snapshot prices = median of ±5 min closes.
4. **Drop bad rows** — holiday/3-day gold weekends, venue-weekends with >5% missing minutes, and stale quotes (no trade >10 min).
5. **Answer Q1–Q5** with Wilson intervals for hit rates and bootstrap CIs for slopes (10,000 resamples).
6. **Honesty checks** — split by token/venue, drop known case-study weekends, shuffled-weekend + weekday placebos, Sat-noon *partial-weekend* path (not a placebo), alternate gold source (CME via Yahoo `GC=F`).

We pre-registered the questions and formulas **before** looking at results (`PREREGISTRATION.md`). Work added after first results is labeled **exploratory**.

---

## 4. The math (without the jargon)

All prices below are in **USD**.

| Name | Plain English | Formula |
|------|---------------|---------|
| **Normal gap** (`B_weekday`) | How much the token usually sits above/below gold on weekdays | Median of `(Token / Gold − 1)` over the prior Mon–Fri |
| **Weekend dislocation** (`D`) | Extra gap that appeared over the weekend, after removing that usual premium | `(Token_just_before_reopen / Gold_Friday − 1) − B_weekday` |
| **Weekend token move** (`W`) | How much the token itself moved Fri → almost-Sunday-open | `Token_pre / Token_Friday − 1` |
| **Gold reopen gap** (`Gap`) | How much gold jumped when it reopened (we use +15 min; also check +5 and +60) | `Gold_reopen / Gold_Friday − 1` |
| **Snap-back** (`R`) | How much the token moved after gold reopened (+1h and +4h) | `Token_after / Token_pre − 1` |

**Two simple tests for “does gold follow?”**

1. **Hit rate** — On what % of weekends did gold and the token move in the **same direction**? A coin flip is 50%. We report a **Wilson 95% CI** (better for small n).
2. **Slope** — Fit a line: `Gold gap ≈ a + b × Token weekend move`.  
   - `b = 1` → gold fully followed the token  
   - `b = 0` → gold ignored the token  
   - Our v2.1 estimate is about **0.65** → gold moved in the same direction, on average about two-thirds as far.

**Who closes a large gap?**  
On weekends where `|D| > 0.25%`, we report **median** and **pooled** shares (means of ratios explode when `D` is small):

- share closed by **gold moving** ≈ `Gap / D`
- share closed by the **token snapping back** ≈ `−R / D`

---

## 5. The data

| What | Source | Notes |
|------|--------|--------|
| Real gold (1-min) | Dukascopy XAU/USD | Primary “truth” for Friday close and Sunday reopen |
| Gold cross-check | Yahoo Finance `GC=F` (hourly) | CME futures proxy; sign agreement with Dukascopy ≈ **84%** |
| Tokens (1-min) | Binance PAXG (`data-api.binance.vision`); OKX XAUT & PAXG | Only venues that contribute rows in v2.1 |
| Bybit XAUT/PAXG | Attempted | Geo-blocked (HTTP 403) → no rows |
| Kraken PAXGUSD | Attempted | History too short via free REST → no rows |
| Stablecoin → USD | Bitstamp USDT/USDC | Full history; rate=1.0 fallback ≈ **0.00%** |
| Crypto stress | Binance BTCUSDT | “Crypto-crash” weekend = BTC Fri→Sun &lt; −5% |
| News labels | `data/events.csv` | GDELT suggestions only until hand-confirmed (**n confirmed = 0**) |

**Sample after filters (study end 2026-11-13):** **85 weekends**, **208** venue×token rows (Binance + OKX). That is still a **small** sample — treat every subgroup carefully.

---

## 6. What we found (headline numbers — v2.1)

| Question | Short answer |
|----------|--------------|
| **How far do tokens drift?** | Typical weekend dislocation ≈ **0.01%**. Most weekends sit between about **−0.55%** and **+0.71%**. Largest absolute move in sample ≈ **2.4%**. |
| **Does gold follow?** | Same direction **72.6%** of the time (Wilson 95% CI **62.3–81.0%**, n=84). Slope ≈ **0.65**. |
| **Who closes big gaps?** | On `|D|>0.25%` (n=45): median gold share +4h **46%**, token **24%**; pooled gold **22%**, token **76%**. OKX looks more gold-led than Binance (exploratory). |
| **News vs quiet?** | News/quiet splits are **provisional** (0 hand-confirmed labels). Crypto-crash weekends are too few to trust (n=3). |
| **Biggest dislocations?** | Top of the list includes **2025-01-31** Binance PAXG (~3.9% D) — see [`findings.md`](findings.md). |

**Honesty checks that matter:**

- Dropping known case-study weekends → hit rate **74.1%** (stable).
- PAXG vs XAUT and Binance vs OKX hit rates are similar (~72–74%); slopes differ more (OKX/XAUT steeper).
- **Shuffled pairing placebo** → null mean **50.3%**; **p < 1/10001**.
- **Weekday placebo** (Thu→Fri token vs Sunday gap) → **48.8%** (coin flip).
- Fri→Sat noon token move vs Sunday gap is a **partial-weekend signal** (~56%), **not** a placebo — it is part of the same weekend path (see PREREGISTRATION amendment).

**Exploratory (labeled as such):** bigger `|W|` → higher hit rate (moves >0.5%: **86%**, n=22); up moves hit more often than down moves (+23 pp, bootstrap CI +4 to +42). Manipulation Links 1–4 stay **pending labels** until `events.csv` is hand-confirmed.

---

## 7. What this means (and what it does *not* mean)

**It means:**

- Tokenized gold is **not glued** to Friday’s gold price over the weekend. Typical drifts are tiny; multi-percent moves happen sometimes (especially on single venues).
- When the token moves over the weekend, Sunday’s gold open **often** goes the same way — clearly above a coin flip in this sample — and on average about **two-thirds** as far (slope ~0.65).
- Real placebos (shuffle + weekday) sit near 50%, which is what you want if the Sunday pairing is doing real work.

**It does *not* mean:**

- There is a proven, cost-surviving trading edge. We did **not** model fees, spreads, slippage, or size.
- You should buy or sell the token every Friday. This paper does not back that.
- Someone is successfully “faking” gold opens for profit. The manipulation thesis’s four links are **untested until labels are confirmed** — do not read “pending” as “disproven” or “proven.”
- The result will hold forever. ~85 weekends is thin; 2025–2026 gold structure changed a lot.

**Sensible takeaway:** Weekend tokenized-gold prices are an **interesting, imperfect preview** of where gold might open — useful for curiosity and for designing a careful *future* strategy test, not a green light to trade today.

---

## 8. Limitations (read these)

1. Small sample (~one weekend per week).
2. Regime change (gold price path, new gold perps, stress episodes).
3. News labels not hand-confirmed (n confirmed = 0).
4. Bybit and Kraken contribute no rows → results lean on Binance + OKX.
5. No historical order-book depth → cannot honestly cost a trade yet (`record_weekends.py` is collecting that going forward).
6. Correlation ≠ causation.

---

## 9. Where to look next

| File | Why |
|------|-----|
| [`findings.md`](findings.md) | Full Q1–Q5 write-up with CIs |
| [`x_article.md`](x_article.md) | Published long-form article |
| [`manipulation_test.md`](manipulation_test.md) | Four-link thesis (pending labels) |
| [`figures/`](figures/) | Histograms, scatter, who-closes, event study |
| [`../data/events.csv`](../data/events.csv) | Confirm news/quiet labels by hand |
| [`../STRATEGY_PHASE.md`](../STRATEGY_PHASE.md) | Later: costs, frozen rules, out-of-sample only |
| [`../data/processed/weekends.parquet`](../data/processed/weekends.parquet) | Reusable table (local; not in git) |

---

*Research only. Not financial advice.*
