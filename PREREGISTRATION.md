# Pre-registration — Gold Weekend Study

> Written 2026-11-16, before results; committed 2026-11-17. v2 additions are exploratory.

Frozen **before** looking at weekend-panel results. Any test added later is labeled **exploratory**.

## Research questions

1. How far do tokenized gold tokens (XAUT, PAXG) drift from gold over the weekend?
2. When tokens move over the weekend, does gold follow at the Sunday reopen?
3. Who closes the gap — gold catching up, or the token snapping back?
4. Is it different on news vs quiet vs crypto-crash weekends (and pre/post Jan 2026)?
5. What were the biggest weekend dislocations, and what happened next?

## Null framing

We try hard to find **no** clear pattern. Same-sign hit rates near 50%, slopes near 0, and thin subgroups are expected outcomes — report them honestly.

## Sample

- Start: first complete Friday on/after 2025-01-01.
- End: latest complete weekend, or `study_end_date` once set for the `v1-study` freeze.
- Unit of observation for inference: weekend (venues on the same weekend are related; report per-venue and pooled descriptives, do not treat every venue-row as independent for hit-rate CIs without noting clustering).
- Exclude holiday / 3-day gold weekends from **main** results; show separately.
- Drop venue-weekend rows with >5% missing weekend minutes; report how many dropped.

## Variable definitions

| Symbol | Definition |
|--------|------------|
| Friday close | Fri 17:00 America/New_York |
| Sunday reopen | Sun 18:00 ET (= 23:00 UTC winter / 22:00 UTC summer) |
| `T_pre` | Token USD price at reopen − 5 minutes |
| `B_weekday` | Median weekday `(T/G − 1)` over the prior Mon–Fri |
| `D` | `(T_pre / G_fri − 1) − B_weekday` |
| `W` | `T_pre / T_fri − 1` |
| `Gap_k` | `G_open(+k min) / G_fri − 1` for k ∈ {5, 15, 60}; **primary k = 15** |
| `R_1h`, `R_4h` | Token return from `T_pre` to reopen + 1h / +4h |
| News | Manual `events.csv` label; GDELT count is suggestion only |
| Crypto-crash | BTC Fri→Sun return < −5% |
| Regime | `pre_2026` if Friday < 2026-01-01 else `post_2026` |

## Decision thresholds (descriptive, not trading)

- Q2 “coin flip” reference: 50% same-sign hit rate.
- Q3 “large drift” filter: `|D| > 0.25%`.
- Subgroup claims require **N ≥ 10** weekends; otherwise “too thin to trust.”
- Bootstrap: 10,000 resamples, seed 42, for hit-rate and slope CIs.
- No trading rules, no costed PnL, no multi-parameter search in this study.

## Honesty checks (pre-registered)

1. PAXG and XAUT separately; at least two venues — say if they disagree.
2. Drop known case-study Fridays listed in `config.yaml` — say if the result depends on them.
3. Placebo: fake reopen Saturday 12:00 ET — Q2 hit rate should be near 50%.
4. If any result looks surprisingly strong, check timezones, stale prices, and USDT/USD drift before reporting.

## Amendment (2026-11-17, after v1 results — exploratory)

**Placebo rename:** The Saturday-noon check (honesty #3) is a *partial-weekend signal* (Fri close → Sat 12:00 ET token move vs Sunday Gap), not a true placebo — it is part of the same weekend path. True placebos used in v2+ are: (a) shuffled pairing of W with another weekend’s Gap; (b) weekday token move (Thu→Fri) vs Sunday Gap. The Sat-noon statistic is still reported for transparency, labeled partial-weekend.

## Out of scope (strategy phase)

Costs, slippage, order-book depth, pre-registered trading rules, and out-of-sample weekends after `study_end_date` belong in `STRATEGY_PHASE.md` only.
