# The Gold Market Closes for 48 Hours Every Weekend. Its Tokens Don't. Can That Be Gamed?

*I tested a market-manipulation theory on 85 weekends of tokenized gold data. Here's everything I found, including where I almost fooled myself.*

---

## The 48-hour hole in the gold market

Every Friday at 5:00pm New York time, the global gold market goes quiet. London over-the-counter dealers stop quoting, CME gold futures close, and for about 48 hours there is no official gold price. Trading resumes Sunday at 6:00pm ET, when CME Globex and the Asian dealers reopen.

Tokenized gold never stops. **XAUT** (Tether Gold) and **PAXG** (Paxos Gold) each represent one troy ounce of physical gold in a vault, and they trade 24/7 on crypto exchanges.

On weekdays, arbitrage keeps the tokens close to real gold: if PAXG trades too far below gold, institutions can buy tokens and redeem them with Paxos for metal (and the reverse when it trades above). But Paxos only creates and redeems PAXG during London gold market hours, from Sunday 6pm ET to Friday 5pm ET. **On weekends, nothing ties the token to the metal.** The price is whatever buyers and sellers on crypto exchanges agree on.

And these are small markets. XAUT's market cap is around $3.3 billion. On a typical day it trades about $1.2 billion, but only around $97 million of that is actual spot tokens; the rest is derivatives. For comparison, the physical gold market turns over roughly **$229 billion a day** OTC plus **$187 billion** on exchanges. XAUT spot is about 0.02% of that, and earlier this year about $4 million of orders could move XAUT 0.5% across the major venues.

---

## The theory

That setup made me wonder about a specific scenario:

> A large firm sells tokenized gold on thin weekend order books, pushing the price down. Retail traders see "gold falling" over the weekend and position for a weak open. When gold reopens Sunday night, it opens lower than it should. The firm, which spent a little moving the token, buys real gold at a discount.

Is that happening? Could it even work?

For the theory to hold, four things all need to be true:

1. **Tokens can move a lot without real news**: someone can push them around.
2. **Those moves drag gold's Sunday open with them.**
3. **The open ends up below fair value**, so gold should bounce back afterwards. That bounce is the "discount."
4. **Identifiable wallets sell into the weekend move and buy back afterwards.**

If step 2 or 3 fails, the profit mechanism doesn't exist, even if someone *can* move the token.

I built an open-source study to test as much of this as public data allows.

---

## What I measured

The sample is every weekend from **January 3, 2025 to November 13, 2026: 85 weekends** after removing 13 holiday weekends, when gold markets close early or stay shut.

**Data:**
- **Gold:** Dukascopy spot XAU/USD, minute by minute, cross-checked against CME gold futures (GC=F)
- **Tokens:** PAXG on Binance, and XAUT and PAXG on OKX, minute by minute
- **Stablecoins:** tokens trade against USDT, so every price was converted to dollars using full-history USDT/USD rates from Bitstamp
- **Crypto context:** Bitcoin's weekend return, to flag crypto-crash weekends

**For each weekend I calculated:**
- **Weekend token move:** from Friday 5pm ET to 5 minutes before the Sunday reopen
- **Weekend dislocation:** how far the token drifted from Friday's gold price, *after subtracting the token's normal weekday premium or discount*. Tokens often trade slightly above or below spot for structural reasons, so this isolates the weekend part.
- **Gold reopen gap:** spot gold from Friday close to 15 minutes after the Sunday reopen. The first minutes of trading are noisy, so 15 minutes gives a cleaner price.
- **Snap-back:** how much the token reversed in the 1 and 4 hours after gold reopened

Each price is the median over a short window rather than a single trade, so one odd print can't distort a weekend. Quotes with no trade for more than 10 minutes are thrown out as stale, and so is any exchange-weekend missing more than 5% of its minute data.

**Ground rules:** I wrote down the questions, definitions and pass/fail thresholds before running the analysis, and committed them to the repo. Anything I added after seeing results is labeled *exploratory*. That includes most of the manipulation-specific tests.

---

## Finding 1: Weekend tokens drift very little

In a typical weekend the tokens barely move away from Friday's gold price. The median dislocation is **0.01%**. Most weekends sit between **−0.55% and +0.71%**, and the largest weekend-average move in the sample was about 2.4%.

There's no sign of a regular weekend discount or premium. Tokens aren't routinely "cheap on Sundays."

[Chart: q1_drift_hist.png]

---

## Finding 2: Tokens are a decent early read of gold's Sunday open

When the tokens moved over the weekend, gold's Sunday reopen went **the same direction 73% of the time** (61 of 84 weekends; 95% confidence range 62–81%). A coin flip would be 50%.

Gold also tends to move about **two-thirds as far** as the token did (slope 0.65, confidence range 0.36–0.96). A slope of 1 would mean gold matched the token exactly; 0 would mean gold ignored it.

[Chart: q2_scatter.png]

**Does it hold up?**

| Check | Result |
|---|---|
| PAXG only | 72.6% |
| XAUT only | 71.4% |
| Binance only | 73.8% |
| OKX only | 72.7% |
| Excluding the weekends I'd read about before starting | 74.1% |
| CME futures vs spot gold agree on the Sunday gap direction | 84% |

Same answer across tokens and exchanges.

**Fake tests that *should* fail:**
- **Shuffled weekends:** pair each weekend's token move with a *different* weekend's gold gap, 10,000 times. Average: **50.3%**. Not one shuffle reached 73%.
- **Weekday window:** use the token's Thursday→Friday move instead. Gold is open then, so that information is already in the price. Result: **48.8%**.

Both came out as coin flips. Whatever the tokens are picking up, it's specific to the weekend, when gold itself is closed.

**When does the information arrive?** Using only the token move from Friday close to *Saturday noon*, the match rate drops to **56%**. Most of the useful movement happens Saturday afternoon through Sunday, which fits weekend news gradually being priced in.

For context: a [Blockworks study of tokenized *stocks*](https://blockworks-research.beehiiv.com/p/when-markets-sleep) found weekend prices barely beat a coin flip (50.7%) at predicting Monday's open. Gold tokens do much better. And a [CoinGecko review](https://www.coingecko.com/learn/tokenized-gold-price-signal) of 16 hand-picked eventful weekends found about two-thirds directional agreement. This study covers *every* weekend, not just the dramatic ones, and lands a bit higher.

---

## Finding 3: Bigger moves are better signals

This was the clearest pattern in the data:

| Weekend token move | Weekends | Gold opened the same way | 95% range |
|---|---|---|---|
| Under 0.25% | 45 | 64% | 50–77% |
| 0.25% – 0.5% | 17 | 76% | 53–90% |
| 0.5% – 1% | 15 | 80% | 55–93% |
| Over 1% | 7 | 7 of 7 | 65–100% |
| **Over 0.5% (combined)** | **22** | **86%** | **67–95%** |

[Chart: q2_hit_by_magnitude.png]

Small moves are mostly noise. Big ones almost always line up with gold's open. The likely reason: big weekend moves are driven by real news like geopolitics, the Fed or tariffs. Gold reacts to the same news when it reopens; the tokens just get there first.

The biggest weekends in the sample fit that pattern:

- **Weekend of Jan 30, 2026:** tokens fell about 1.6–2%, then gold gapped down **3.1%** at the reopen and kept falling. This came right after the late-January gold sell-off, and Bitcoin also crashed that weekend.
- **Weekend of Feb 27, 2026:** tokens rose about 1.6–2.5%; gold gapped up **1.3%**. This was the weekend of the strikes on Iran.
- **Weekend of Jun 20, 2025:** tokens rose about 1.5%; gold gapped up **0.3%**. This was the weekend of the US strikes on Iran's nuclear sites.

*(The catalysts are context from the news, not hand-confirmed study labels yet; see "What I can't answer yet" below.)*

---

## Finding 4: Drops are less reliable than rallies

This is the finding most relevant to the "fake crash" theory.

- When tokens **rose** over the weekend, gold opened higher **84%** of the time (44 weekends)
- When tokens **fell**, gold opened lower only **61%** of the time (41 weekends)
- The gap is about **23 percentage points** (95% range 4–42)

In other words, weekend *drops* in tokenized gold are a noticeably weaker signal than weekend rallies. More of them turn out to be noise that gold doesn't follow.

That's consistent with tokens sometimes being **sold for reasons unrelated to gold**, for example crypto traders raising cash or meeting margin calls during a crypto sell-off. It would also be consistent with deliberate selling, but this data can't tell those apart. This was an exploratory test, so it's a lead to follow up, not a conclusion.

---

## Finding 5: Who closes the gap — gold or the token?

When the token drifts meaningfully from gold (more than 0.25%, 45 weekends), the gap closes in one of two ways. Either gold catches up at the reopen, meaning the token was right. Or the token snaps back, meaning it was noise.

On a typical weekend, measured 4 hours after the reopen:
- **Gold closed about 46%** of the gap
- **The token reversed about 24%**
- The gap shrank by more than half within 4 hours on **40%** of these weekends: gold did most of the work on 22%, the token on 18%

So more often than not, gold moves toward the token rather than the other way round. That's what you'd expect if the tokens are mostly picking up real information.

There's one notable exception. **On the weekend of Jan 31, 2025, PAXG on Binance jumped 3.9%** while XAUT on OKX moved only 0.8% and gold opened essentially flat (+0.07%). Within four hours of the reopen, Binance PAXG had fallen back 4.5%. That's what a single-exchange dislocation looks like: one venue moved, nothing else did, and the token snapped back. It was an *up* move, not a down move, and it's the only weekend of its kind in the clean data. Note that this one weekend also skews any "pooled" average of who closes the gap, which is why the typical-weekend (median) numbers above are the better guide.

---

## Finding 6: No sign of a systematic "cheap open"

Step 3 of the theory says gold should *bounce* after an artificially low open, so the buyer captures a discount. I checked gold's move from the reopen to Monday's London open (3am ET), the London morning price, and Monday's 5pm ET close.

- **Ordinary weekends (81):** gold drifted about **+0.14%** by the London open (95% range −0.01% to +0.30%). That's statistically indistinguishable from zero.
- **Weekends where tokens fell on real news (4):** gold **kept falling**, by about **−2.6%** by the London open and still −1.2% by Monday's close. The weekend drop was real, not a discount.

In this data there's no regular pattern of gold opening cheap and recovering. The "quiet weekend, tokens pushed down" group, the exact scenario in the theory, can't be isolated yet (see below).

---

## Finding 7: The link got stronger in 2026

Splitting the sample at the start of 2026:

| Period | Weekends | Same-direction rate | Slope |
|---|---|---|---|
| 2025 | 46 | 71% | **0.25** |
| 2026 | 39 | 74% | **0.84** |

The direction match is similar, but the *size* relationship is much tighter in 2026. Gold now follows about 85% of the token's weekend move vs about 25% before. Plausible reasons: more weekend liquidity in gold tokens, new 24/7 gold derivatives launched in early 2026, and a much more volatile gold market (from about $2.6k to a peak near $5.5k and back to about $4k). The confidence ranges overlap a little, so treat this as a trend worth watching.

---

## So — can you fake a weekend gold crash?

| Step | What the data says |
|---|---|
| 1. Tokens move a lot without news | **Not tested yet.** Needs hand-labeled news/quiet weekends |
| 2. Those moves drag gold's open | When gold follows tokens, it's mostly on big moves that look news-driven. Drops follow less reliably than rallies. |
| 3. The open is below fair value | **No systematic evidence.** Post-open drift is about zero; after real news drops, gold kept falling |
| 4. Wallets sell and buy back | **Not tested yet.** Needs on-chain analysis of the candidate weekends |

**My honest read so far:** the weekend token market behaves mostly like an early price-discovery venue, not a manipulation playground. Big token moves usually reflect real news that gold then confirms. I found no systematic "cheap open" to exploit.

The one place the theory could still live is **weekend drops being noisier than rallies.** That's exactly what Part 2 will dig into.

---

## How I almost fooled myself

The first version of this study looked *much* more exciting. It showed several dramatic 3–4% "spikes" in PAXG on Binance on quiet weekends that gold completely ignored, with the token snapping back afterwards. That looked like strong support for the manipulation idea.

It was bad data. The download had been pulling from a much thinner exchange feed, and many of those "spikes" were stale prices: hours with no trades, carried forward. After I switched to Binance's official market-data feed and logged the source of every request, nearly all the spikes disappeared. For example, last weekend's "+3.7% spike" became a −0.8% move matching OKX. The striking story went with them.

**Other fixes along the way:**
- **Stablecoin conversion:** the first version effectively treated USDT as exactly $1 everywhere, because the free price history only went back about 720 minutes. Fixed with full-history rates.
- **Stale prices:** quotes with no recent trade are now detected and dropped.
- **Confidence intervals:** now use methods that hold up with small samples.
- **The placebo:** my original "fake Saturday-noon reopen" wasn't a real placebo, because Saturday is part of the weekend. I replaced it with the two proper ones above.

Every change is logged in the repo's research log, with old vs new numbers.

---

## What I can't answer yet (Part 2)

1. **News vs quiet weekends:** every weekend needs a human label of whether gold-relevant news broke between Friday 5pm and Sunday 6pm, assigned *without looking at prices* so the labels can't be biased by the results. Then I can isolate quiet weekends with big token drops: the exact scenario the theory needs.
2. **On-chain flows:** for those weekends, which wallets moved PAXG and XAUT onto exchanges before the drop, and did the same wallets buy back after the open? (Compared against random quiet weekends, and without naming anyone.)
3. **Order-book depth:** I've started recording live weekend order books and liquidations, to measure how much it would actually cost to move these tokens.

---

## Caveats

- **85 weekends is a small sample**, and some groups are smaller than 20. Confidence ranges are wide.
- **The market changed a lot** over the period: new derivatives, much higher volatility, and big swings in the gold price.
- **Correlation isn't causation.** Tokens and gold mostly react to the same news; tokens aren't "causing" gold's open.
- **Only two exchanges contribute usable data**, Binance and OKX. Bybit was geo-blocked from my location and Kraken's free history was too short.
- **Several findings are exploratory:** size buckets, up vs down, post-open drift and the 2025 vs 2026 split were added after the first results.
- **No firm or wallet is accused of anything.** This tests an idea; it isn't an allegation.

---

## Repo

Everything is open source and reproducible with one command (`python3 run_all.py`): data download, cleaning, analysis, charts, preregistration, and a log of every change.

**[GitHub link]**

*Research only. Not financial advice and not a trading signal.*

**Sources:** [Paxos: PAX Gold price determination](https://support.paxos.com/articles/7818174259-pax-gold-price-determination) · [DefiLlama: XAUT](https://defillama.com/token/xaut) · [World Gold Council: trading volumes, Sept 2026](https://www.gold.org/goldhub/research/gold-etfs-holdings-and-flows/2026/10/) · [FalconX: tokenized gold liquidity](https://www.falconx.io/newsroom/from-vault-to-ledger-trends-shaping-the-tokenized-gold-rush) · [Blockworks: When Markets Sleep](https://blockworks-research.beehiiv.com/p/when-markets-sleep) · [CoinGecko: tokenized gold as a Monday signal](https://www.coingecko.com/learn/tokenized-gold-price-signal)
