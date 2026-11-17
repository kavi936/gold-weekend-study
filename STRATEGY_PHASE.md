# Strategy phase (stub — do not implement yet)

This study phase freezes descriptive findings. A later strategy phase may reuse:

- `data/processed/weekends.parquet` — every measured weekend × token × venue quantity
- `data/forward/` — live L2 top-20 snapshots (10s) and Binance liquidation streams from `record_weekends.py`

**Do not** retune study definitions or Q1–Q5 using weekends after `study_end_date`.

## Questions for later

1. **Costs from depth.** From recorded books, what are typical half-spreads, depth-to-size, and slippage for a small tokenized-gold trade near Fri close and near Sun reopen?
2. **Simple pre-registered rules.** At most two free parameters each (e.g. dislocation threshold `x`, exit horizon `k`). Register rules using only study-era evidence (`friday_date ≤ study_end_date`).
3. **Out-of-sample only.** Evaluate net returns only on weekends with `friday_date > study_end_date`.
4. **Paper trading.** Run the frozen rules on live weekends for a fixed number of weekends before any real capital.
5. **Contamination firewall.** Never reopen Q1–Q5 charts or labels using OOS weekends; keep recorder data out of the descriptive study pipeline.

## Freeze checklist (when publishing the study)

1. Set `study_end_date` in `config.yaml` to the Friday of the last included weekend.
2. Re-run `python run_all.py --phase all` so reports match the freeze.
3. Tag: `git tag -a v1-study -m "Freeze descriptive gold weekend study"` (only when asked to publish).
4. Start / keep `record_weekends.py` running so post-freeze weekends accumulate depth.
