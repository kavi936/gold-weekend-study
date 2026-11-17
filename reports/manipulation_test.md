# Manipulation thesis test (EXPLORATORY)

Added in v2 after seeing results — **not preregistered**. News/quiet labels are **provisional** until `events.csv` is hand-confirmed.

Thesis under test: *someone pushes weekend tokens to make gold look weaker, gold opens cheap, they buy the open.*
All four links must hold. Failure of Link 2 or 3 means the profit mechanism does not operate, even if Link 1 holds.

## Verdict

| Link | Status | Detail |
|------|--------|--------|
| 1 Tokens move without news | **pending labels** | n confirmed labels = 0 — confirm events.csv before judging Links 1–4 |
| 2 Move transmits to gold reopen | **pending labels** | n confirmed labels = 0 — confirm events.csv before judging Links 1–4 |
| 3 Gold opens below fair / recovers | **pending labels** | n confirmed labels = 0 — confirm events.csv before judging Links 1–4 |
| 4 On-chain flows | **pending labels** | n confirmed labels = 0 — confirm events.csv before judging Links 1–4 |

## Link details

- Link 1 candidates (|D|>1%, quiet, not stale): {'n_candidate_rows': 0, 'n_candidate_weekends': 0, 'by_venue_token': {}, 'n_market_wide': 0, 'n_single_venue': 0, 'provisional_labels': True, 'exploratory': True}
- Link 2 shares: {'all_candidates': {}, 'market_wide': {}, 'single_venue': {}, 'by_venue': {}, 'exploratory': True, 'note': 'Thesis needs high gold share on quiet token-led moves.'}
- Link 3 post-open drift: {'after_quiet_token_down': {'n': 0}, 'after_news_token_down': {'n': 4, 'to_mon_03et': {'mean': -0.02643533850659016, 'lo': -0.05137298092347403, 'hi': -0.003159732118399705, 'n': 4}, 'to_lbma_am_approx': {'mean': -0.01603941706129383, 'lo': -0.03648048791864103, 'hi': -0.0022207046754531, 'n': 4}, 'to_mon_17et': {'mean': -0.012229546889703569, 'lo': -0.01992332653511114, 'hi': -0.004535767244295996, 'n': 4}}, 'after_other': {'n': 81, 'to_mon_03et': {'mean': 0.0014408884732584717, 'lo': -0.00014409665869673168, 'hi': 0.0030275824832903526, 'n': 81}, 'to_lbma_am_approx': {'mean': 0.0010863244898524816, 'lo': -0.0007862727810189617, 'hi': 0.002925186851717268, 'n': 81}, 'to_mon_17et': {'mean': 0.001960194526710024, 'lo': -0.0009940596383739206, 'hi': 0.004962840886927387, 'n': 80}}, 'after_quiet_token_up_symmetry': {'n': 0}, 'provisional_labels': True, 'exploratory': True, 'note': 'Efficient-market null: mean post-open drift ≈ 0 for all groups.'}
- Link 4: {'verdict': ('untestable', 'no candidate weekends'), 'note': 'No quiet |D|>1% candidates after Part A filters.', 'exploratory': True}

**No wallet owners or firms are named.** On-chain results, if added later, use wallet A/B only.
