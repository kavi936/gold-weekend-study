# What Happens to Tokenized Gold Over the Weekend?

Gold markets close **Friday 17:00 ET** and reopen **Sunday 18:00 ET**. Tokenized gold (XAUT, PAXG) keeps trading on crypto exchanges all weekend with **no mint/redeem anchor** to physical gold.

This study asks whether weekend token prices tell us anything about gold's Sunday open, and tests a speculative idea: *could someone push tokens down on thin weekend books to make gold open cheap?*

It is a **descriptive research study**, not a trading strategy and not financial advice.

**Start here:** [`reports/findings.md`](reports/findings.md) (all numbers) · [`reports/manipulation_test.md`](reports/manipulation_test.md) (the four-link test of the manipulation idea) · [`PREREGISTRATION.md`](PREREGISTRATION.md) (definitions frozen before analysis)

## Key results (85 weekends, Jan 2025 → 2026-11-13)

| Question | Answer |
|---|---|
| How far do tokens drift from gold over a weekend? | Median **0.01%**; most weekends between −0.55% and +0.71% |
| Does gold's Sunday open follow the weekend token move? | Same direction **72.6%** of weekends (Wilson 95% CI 62–81%, n=84); slope **0.65** |
| Placebos (should be ~50%) | Shuffled weekends **50.3%** (p < 1/10001); weekday window **48.8%** |
| Does size matter? *(exploratory)* | Moves under 0.25% → 64%; over 0.5% → **86%** (n=22) |
| Up vs down *(exploratory)* | Rallies 84% vs drops 61%; difference +23 pts (CI +4 to +42) |
| Systematic "cheap open"? *(exploratory)* | No: gold's post-open drift to Monday London ≈ +0.14% (CI includes 0) |
| Manipulation thesis (Links 1–4) | **Pending**: needs hand-confirmed news labels + on-chain analysis |

Venues contributing data: Binance (PAXG), OKX (XAUT, PAXG). Gold: Dukascopy, cross-checked against CME GC=F (84% sign agreement).

## Method (plain English)

For each weekend we measure:

- The token's **usual** weekday premium/discount to gold, subtracted so only the **weekend** part remains.
- The token move from Friday close to 5 minutes before Sunday reopen, using median prices in short windows to avoid single-trade wicks.
- Gold's move from Friday close to reopen + 15 minutes (+5 and +60 as sensitivity checks).
- How much the token snapped back 1–4 hours after the reopen.

Prices are converted from USDT to USD with full-history Bitstamp rates. Stale quotes (no trade for >10 min) and venue-weekends missing >5% of minutes are dropped. Holiday weekends are excluded from the main results. Hit rates use Wilson intervals; slopes use bootstrap CIs (10,000 resamples).

Anything added after the first results is labeled **exploratory**. Version notes live in [`reports/findings.md`](reports/findings.md) ("What changed").

## Quick start

```bash
python3 -m pip install -r requirements.txt
python3 run_all.py --phase all      # fetch → clean → weekends → analysis → report
python3 -m pytest -q
```

Raw downloads are cached under `data/raw/` and not committed. The fetch is fully scripted.

## News labels

[`data/events.csv`](data/events.csv) has one row per weekend. GDELT provides suggestions only. A weekend counts as **news** only if a dated source shows a gold-relevant event between Fri 17:00 and Sun 18:00 ET, labeled **without looking at prices**. Labels are not yet confirmed, so news/quiet splits are provisional.

## Forward recorder (separate from the study)

`record_weekends.py` records weekend order-book depth and liquidations for a possible later strategy phase. The study never reads `data/forward/`. It needs an always-on machine. See [`STRATEGY_PHASE.md`](STRATEGY_PHASE.md).

## Data sources

| Series | Source |
|---|---|
| Gold 1-min | Dukascopy XAU/USD |
| Gold cross-check | Yahoo Finance `GC=F` (hourly) |
| Tokens 1-min | Binance (`data-api.binance.vision`), OKX |
| USDT/USDC → USD | Bitstamp |
| BTC weekend return | Binance BTCUSDT |
| News suggestions | GDELT DOC API |

Bybit (geo-blocked) and Kraken (short history) were attempted and contribute no rows.

## Caveats

- 85 weekends is a small sample; several subgroups are under 20.
- The gold market changed sharply over 2025–2026.
- Correlation is not causation: tokens and gold mostly react to the same news.
- No firm or wallet is accused of anything.
- Not financial advice.
