# Gold Weekend Study — Findings (v2.1)

_Generated from `weekends.parquet`. study_end_date = `2026-11-13`._

## What changed from v1 → v2 → v2.1

- Full-history USDT/USD via Bitstamp (Kraken ~720-bar cap fixed).
- USDT conversion rate=1.0 fallback now **0.00%** of minutes (target <1%).
- Stale snapshots (>10 min since last trade) dropped: **12** rows.
- Snapshot prices = median of ±5 min closes (point prices kept as sensitivity).
- Q3 uses **median + pooled** shares (not means of ratios).
- Sat-noon renamed **partial-weekend signal**; real placebos = shuffled pairing + weekday move.
- Failed GDELT → `unknown` (never silent `quiet`). New tests labeled **exploratory**.
- **v2.1:** Binance = `data-api.binance.vision` only (no Binance.US mix); Wilson CIs; up−down bootstrap CI; Q3 per-venue / leave-out 2025-01-31; chart footers = contributing venues; Links 1–4 = pending labels when n confirmed = 0.

## TL;DR

- **v2.1** sample: **85** weekends (208 venue×token rows after coverage/holiday/**stale** filters). Venues: binance, okx.
- Weekend dislocation D median **0.01%** (10th–90th: -0.55% to 0.71%).
- Same-sign hit rate: **72.6%** (Wilson 95% CI 62.3%–81.0%); coin-flip = 50%.
- Slope: **0.65** (CI 0.36–0.96).
- Q3 (v2): median gold share +4h **46%**, token **24%**; pooled gold **22%**.
- News/quiet splits are **PROVISIONAL** (n confirmed labels = 0).

## Q1 — How far do the tokens drift?

**Answer:** Typical weekend dislocation ≈ 0.01% (p10–p90 -0.55% to 0.71%); largest absolute ≈ 2.37%.

- N weekends: 84 · Chart: `figures/q1_drift_hist.png`

## Q2 — Does gold follow the token?

**Answer:** Same-sign hit rate **72.6%** (Wilson 95% CI 62.3%–81.0%; n=84, k=61). Slope **0.65** (bootstrap CI 0.36–0.96).

- Chart: `figures/q2_scatter.png` · Headline exploratory chart: `figures/q2_hit_by_magnitude.png`

## Q3 — Who closes the gap? (v2 method)

**Answer:** On |D|>0.25% (n=45): median gold share +4h 46%, token 24%; pooled gold 22%, token 76%. |gap| shrank >50% within 4h on 40% of those weekends (gold-led 22%, token-led 18%).

### Q3 sensitivity (exploratory v2.1)

- venue **binance** (n=51): median gold/token +4h 32% / 5%; pooled 24% / 77%
- venue **okx** (n=37): median gold/token +4h 57% / 27%; pooled 40% / 100%
- without 2025-01-31 (n=44): median gold/token +4h 47% / 22%; pooled 34% / 46%

## Q4 — Weekend types (**provisional** news/quiet)

| group         |   n | too_thin   | provisional   | note                                        |   hit_rate |     hit_lo |     hit_hi |      slope |      slope_lo |   slope_hi |   token_share_1h_median |   gold_share_1h_median |
|:--------------|----:|:-----------|:--------------|:--------------------------------------------|-----------:|-----------:|-----------:|-----------:|--------------:|-----------:|------------------------:|-----------------------:|
| all           |  85 | False      | False         |                                             |   0.72619  |   0.622524 |   0.810073 |   0.652902 |   0.357879    |   0.963526 |              -0.0623875 |               0.457687 |
| news          |  14 | False      | True          | PROVISIONAL until events.csv hand-confirmed |   0.571429 |   0.325903 |   0.786195 |   1.247    |  -0.167907    |   1.59117  |               0.302946  |               0.528349 |
| quiet         |   0 | True       | True          | PROVISIONAL until events.csv hand-confirmed | nan        | nan        | nan        | nan        | nan           | nan        |             nan         |             nan        |
| unknown_label |  71 | False      | False         |                                             |   0.757143 |   0.645047 |   0.842483 |   0.489573 |   0.29242     |   0.730283 |              -0.0623875 |               0.457687 |
| crypto_crash  |   3 | True       | False         |                                             |   1        |   0.438494 |   1        |   1.45479  |   7.71951e-07 |   1.92572  |              -0.815834  |               1.27529  |
| pre_2026      |  46 | False      | False         |                                             |   0.711111 |   0.566312 |   0.822701 |   0.250656 |   0.0546307   |   0.680241 |               0.0345116 |               0.295708 |
| post_2026     |  39 | False      | False         |                                             |   0.74359  |   0.58918  |   0.854314 |   0.844444 |   0.508922    |   1.18444  |              -0.105812  |               0.801686 |

## Q5 — Top 10 dislocations

| friday_date   | token   | venue   |          D |          W |       Gap_15 |         R_1h |        R_4h | label   | catalyst   | source_url   | crypto_crash   |
|:--------------|:--------|:--------|-----------:|-----------:|-------------:|-------------:|------------:|:--------|:-----------|:-------------|:---------------|
| 2025-01-31    | PAXG    | binance |  0.0391763 |  0.0378997 |  0.000665622 | -0.0326282   | -0.0453479  | unknown |            |              | False          |
| 2026-02-27    | PAXG    | binance |  0.0248216 |  0.0246863 |  0.0134688   |  0.000923538 | -0.00586372 | unknown |            |              | False          |
| 2026-02-27    | PAXG    | okx     |  0.0245187 |  0.0243569 |  0.0134688   |  0.00143592  | -0.00591183 | unknown |            |              | False          |
| 2026-01-23    | PAXG    | binance |  0.017719  |  0.0198044 |  0.00670831  | -0.00568596  |  0.00229979 | unknown |            |              | False          |
| 2026-01-23    | PAXG    | okx     |  0.0174869 |  0.0189019 |  0.00670831  | -0.00520686  |  0.00271006 | unknown |            |              | False          |
| 2026-01-30    | XAUT    | okx     | -0.0169722 | -0.0182088 | -0.0305642   | -0.0137758   | -0.0217976  | news    |            |              | True           |
| 2026-02-27    | XAUT    | okx     |  0.0164657 |  0.0158715 |  0.0134688   |  0.00174601  | -0.00551396 | unknown |            |              | False          |
| 2026-01-30    | PAXG    | okx     | -0.015906  | -0.0196157 | -0.0305642   | -0.0129232   | -0.0192727  | news    |            |              | True           |
| 2025-06-20    | PAXG    | binance |  0.0159002 |  0.0170307 |  0.00329524  | -0.00950707  | -0.0157093  | unknown |            |              | False          |
| 2026-01-30    | PAXG    | binance | -0.0154342 | -0.0197439 | -0.0305642   | -0.0124881   | -0.0191488  | news    |            |              | True           |

## Honesty checks / placebos

- Partial-weekend (Fri→Sat noon) hit rate: 56.0% — part of the real weekend, not a placebo.
- **Shuffled pairing placebo:** real hit 72.6%; null mean 50.3% (CI 39.3%–60.7%); p < 1/10001 (n_null≥real=0 / 10000).
- **Weekday placebo** (Thu→Fri token vs Sunday gap): 48.8%.
- Stale rows dropped: 12 by venue {'okx': 12}.
- Drop known cases: hit 74.1%.
- GC=F sign agreement: 84% (n=81).
- Confirmed labels: n=0 — news/quiet splits provisional.

### By token / venue

- q2_token_PAXG: hit 72.6%, slope 0.48
- q2_token_XAUT: hit 71.4%, slope 0.87
- venue binance: hit 73.8%, slope 0.48
- venue okx: hit 72.7%, slope 0.79

## EXPLORATORY — magnitude buckets

| bucket           |   n |   hit_rate |   hit_lo |   hit_hi | ci_method   |    slope | exploratory   |
|:-----------------|----:|-----------:|---------:|---------:|:------------|---------:|:--------------|
| <0.25%           |  45 |   0.644444 | 0.498355 | 0.767811 | wilson      | 0.944157 | True          |
| 0.25–0.5%        |  17 |   0.764706 | 0.527378 | 0.904451 | wilson      | 0.648637 | True          |
| 0.5–1%           |  15 |   0.8      | 0.548141 | 0.929526 | wilson      | 0.632586 | True          |
| >1%              |   7 |   1        | 0.645661 | 1        | wilson      | 1.0005   | True          |
| >0.5% (combined) |  22 |   0.863636 | 0.666646 | 0.952511 | wilson      | 0.708608 | True          |

## EXPLORATORY — up vs down

- Down moves: hit 61.0% (Wilson CI 45.7%–74.3%; n=41)
- Up moves: hit 83.7% (Wilson CI 70.0%–91.9%; n=44)
- Hit(up) − hit(down) = 22.7% (bootstrap 95% CI 4.1%–41.7%).

## Holiday weekends (CME / LBMA)

Config `holidays` dates and CME metals / LBMA notes:

| Date | Name | CME metals | LBMA | Our Fri/Mon flag effect |
|------|------|------------|------|-------------------------|
| 2025-01-01 | New Year's Day | Metals closed (Wed) — does not create Fri/Mon 3-day gold weekend by itself | No auction (Wed) | Wed holiday; Fri/Mon adjacency false unless listed Friday/Monday |
| 2025-01-20 | MLK Day | Metals early close / halt (Mon) — abbreviated Mon session, not full 3-day close | US holiday; LBMA usually auctions (UK open) | Mon holiday → weekend Fri 2025-01-17 flagged |
| 2025-02-17 | Presidents' Day | Metals early close / halt (Mon) | US holiday; LBMA usually auctions | Mon → weekend Fri 2025-02-14 flagged |
| 2025-04-18 | Good Friday | Metals FULLY CLOSED (Fri) — true 3-day gold weekend | No auction (Fri); Easter Monday 2025-04-21 also no auction | Fri close → weekend Fri 2025-04-18 flagged (strongest case) |
| 2025-05-26 | Memorial Day | Metals early close / halt (Mon) | UK Spring Bank Holiday — no LBMA auction (Mon) | Mon → weekend Fri 2025-05-23 flagged |
| 2025-06-19 | Juneteenth | Metals early close (Thu 2025) — mid-week, not Fri/Mon adjacency | US holiday; LBMA usually auctions | Thu — our Fri/Mon rule does NOT flag a weekend (correct) |
| 2025-07-04 | Independence Day | Metals early close (Fri) | US holiday; LBMA usually auctions | Fri → weekend Fri 2025-07-04 flagged |
| 2025-09-01 | Labor Day | Metals early close / halt (Mon) | US holiday; LBMA usually auctions | Mon → weekend Fri 2025-08-29 flagged |
| 2025-11-27 | Thanksgiving | Metals early close / halt (Thu) — mid-week | US holiday; LBMA usually auctions | Thu — Fri/Mon rule does NOT flag (correct); day-after may early-close Fri |
| 2025-12-25 | Christmas | Metals CLOSED (Thu) | No auction Christmas + Boxing Day (Thu–Fri) | Thu/Fri cluster — Fri 2025-12-26 is Boxing Day (LBMA); consider adding 2025-12-26 |
| 2026-01-01 | New Year's Day | Metals closed (Thu) | No auction (Thu) | Thu — not Fri/Mon adjacency |
| 2026-01-19 | MLK Day | Metals halt ~2:30 p.m. CT, reopen 6 p.m. (Mon) | US holiday; LBMA usually auctions | Mon → weekend Fri 2026-01-16 flagged |
| 2026-02-16 | Presidents' Day | Metals halt (Mon) | US holiday; LBMA usually auctions | Mon → weekend Fri 2026-02-13 flagged |
| 2026-04-03 | Good Friday | Metals FULLY CLOSED (Fri) — true 3-day gold weekend | No auction (Fri); Easter Monday 2026-04-06 also no auction | Fri → weekend Fri 2026-04-03 flagged (strongest case) |
| 2026-05-25 | Memorial Day / UK Spring Bank | Metals halt (Mon) | No auction (Mon) | Mon → weekend Fri 2026-05-22 flagged |
| 2026-06-19 | Juneteenth | Metals early close (Fri) | US holiday; LBMA usually auctions | Fri → weekend Fri 2026-06-19 flagged |
| 2026-07-03 | Independence Day observed | Metals early close (Fri) | US holiday observed; LBMA usually auctions | Fri → weekend Fri 2026-07-03 flagged |
| 2026-09-07 | Labor Day | Metals halt (Mon) | US holiday; LBMA usually auctions | Mon → weekend Fri 2026-09-04 flagged |
| 2026-11-26 | Thanksgiving | Metals halt (Thu) | US holiday; LBMA usually auctions | Thu — Fri/Mon rule does NOT flag |
| 2026-12-25 | Christmas | Metals CLOSED (Fri) — true long weekend | No auction Christmas (Fri) + Boxing Day observed Mon 2026-12-28 | Fri → weekend Fri 2026-12-25 flagged; also Mon 12-28 LBMA closed |

**Weekends flagged `holiday_weekend=True` in sample (2025-01-01 → 2026-11-13):** 2025-01-17, 2025-02-14, 2025-04-18, 2025-05-23, 2025-07-04, 2025-08-29, 2026-01-16, 2026-02-13, 2026-04-03, 2026-05-22, 2026-06-19, 2026-07-03, 2026-09-04

**Verification notes (v2.1):**
- True full gold closes that match the study’s 3-day-weekend intent: **Good Friday** (2025-04-18, 2026-04-03) and **Christmas 2026-12-25** (Fri).
- Many US Mon holidays are CME metals *early close / midday halt*, not a full Friday–Monday gold blackout; Dukascopy may still have quotes. We still exclude them as configured (conservative) and report holiday-only Q2/Q3 separately.
- Mid-week holidays (NYD Wed/Thu, Thanksgiving Thu, Juneteenth 2025 Thu) do **not** trip Fri/Mon adjacency — expected.
- Optional adds (not required for v2.1): LBMA **Easter Monday** (2025-04-21, 2026-04-06), **Boxing Day 2025-12-26**, **Boxing Day observed 2026-12-28**, UK Early May / Summer Bank.
- Sources: CME trading-hours holiday schedule; ICE LBMA Gold Holiday Calendar 2025/2026 PDFs.

## Manipulation test

See [`manipulation_test.md`](manipulation_test.md) (exploratory). When n confirmed labels = 0, Links 1–4 are **pending labels** (not “not supported”).

## Limitations

- Small sample; regime change; provisional news labels; correlation ≠ causation.
- Bybit geo-blocked; Kraken history short; on-chain Link 4 needs an indexed archive.
