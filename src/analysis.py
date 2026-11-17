"""Q1–Q5 descriptive analysis + honesty checks. No trading rules."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.logging_utils import setup_logging
from src.math_defs import convergence_shares, same_sign


def study_filter(panel: pd.DataFrame) -> pd.DataFrame:
    """Rows used for published findings."""
    m = panel["study_sample"].astype(bool) & panel["included_main"].astype(bool)
    return panel.loc[m].copy()


def _weekend_level(df: pd.DataFrame, how: str = "mean") -> pd.DataFrame:
    """Collapse venue×token rows to one row per weekend (mean of numeric cols)."""
    num = df.select_dtypes(include=[np.number]).columns.tolist()
    keys = ["weekend_id", "friday_date", "label", "crypto_crash", "regime"]
    keys = [k for k in keys if k in df.columns]
    if how == "mean":
        g = df.groupby(keys, as_index=False)[num].mean(numeric_only=True)
    else:
        g = df.groupby(keys, as_index=False).first()
    return g


def bootstrap_ci(values: np.ndarray, stat_fn, n: int, seed: int) -> tuple[float, float, float]:
    """Return (point, lo, hi) for 95% percentile bootstrap CI."""
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    point = float(stat_fn(values))
    stats = np.empty(n)
    for i in range(n):
        sample = rng.choice(values, size=len(values), replace=True)
        stats[i] = stat_fn(sample)
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return point, float(lo), float(hi)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval for a binomial proportion (better for small n)."""
    if n <= 0:
        return np.nan, np.nan, np.nan
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z / denom) * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return float(p), float(max(0.0, center - half)), float(min(1.0, center + half))


def hit_rate_and_ci(w: np.ndarray, gap: np.ndarray, n_boot: int, seed: int) -> dict[str, float]:
    """Hit rate with Wilson CI (primary) and bootstrap CI (secondary)."""
    mask = ~(np.isnan(w) | np.isnan(gap) | (w == 0) | (gap == 0))
    w, gap = w[mask], gap[mask]
    if len(w) == 0:
        return {
            "hit_rate": np.nan, "lo": np.nan, "hi": np.nan, "n": 0,
            "wilson_lo": np.nan, "wilson_hi": np.nan, "k": 0,
        }

    pairs = np.column_stack([w, gap])
    hits = np.array([same_sign(a, b) for a, b in pairs], dtype=float)
    hits = hits[~np.isnan(hits)]
    k = int(np.sum(hits))
    n = int(len(hits))
    point, w_lo, w_hi = wilson_ci(k, n)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        sample = pairs[rng.integers(0, len(pairs), size=len(pairs))]
        h = np.array([same_sign(a, b) for a, b in sample], dtype=float)
        h = h[~np.isnan(h)]
        boots.append(np.mean(h) if len(h) else np.nan)
    lo, hi = np.nanpercentile(boots, [2.5, 97.5])
    return {
        "hit_rate": point,
        "lo": float(w_lo),  # Wilson primary for reporting
        "hi": float(w_hi),
        "bootstrap_lo": float(lo),
        "bootstrap_hi": float(hi),
        "wilson_lo": float(w_lo),
        "wilson_hi": float(w_hi),
        "n": n,
        "k": k,
    }


def slope_and_ci(w: np.ndarray, gap: np.ndarray, n_boot: int, seed: int) -> dict[str, float]:
    mask = ~(np.isnan(w) | np.isnan(gap))
    w, gap = w[mask], gap[mask]
    if len(w) < 3:
        return {"slope": np.nan, "intercept": np.nan, "lo": np.nan, "hi": np.nan, "n": int(len(w))}

    def fit(x, y):
        X = np.column_stack([np.ones(len(x)), x])
        coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        return float(coef[0]), float(coef[1])

    intercept, slope = fit(w, gap)
    rng = np.random.default_rng(seed)
    slopes = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(w), size=len(w))
        _, s = fit(w[idx], gap[idx])
        slopes.append(s)
    lo, hi = np.nanpercentile(slopes, [2.5, 97.5])
    return {"slope": slope, "intercept": intercept, "lo": float(lo), "hi": float(hi), "n": int(len(w))}


def q1_drift(df: pd.DataFrame) -> dict[str, Any]:
    d = df["D"].dropna().values
    if len(d) == 0:
        return {"n": 0}
    return {
        "n": int(len(d)),
        "median": float(np.median(d)),
        "p10": float(np.percentile(d, 10)),
        "p90": float(np.percentile(d, 90)),
        "max": float(np.max(np.abs(d))),
        "max_signed": float(d[np.argmax(np.abs(d))]),
        "values": d,
    }


def q2_follow(df: pd.DataFrame, cfg: dict[str, Any], gap_col: str = "Gap_15") -> dict[str, Any]:
    w = df["W"].values.astype(float)
    gap = df[gap_col].values.astype(float)
    hr = hit_rate_and_ci(w, gap, cfg["bootstrap_samples"], cfg["bootstrap_seed"])
    sl = slope_and_ci(w, gap, cfg["bootstrap_samples"], cfg["bootstrap_seed"])
    return {"hit_rate": hr, "slope": sl, "gap_col": gap_col}


def q3_who_closes(df: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """v2: median + pooled shares (means of ratios explode when D is small)."""
    thr = float(cfg["dislocation_threshold"])
    sub = df.loc[df["D"].abs() > thr].copy()
    out: dict[str, Any] = {"n": int(len(sub)), "threshold": thr, "method": "median_and_pooled_v2"}
    for hours, col in [(1, "R_1h"), (4, "R_4h")]:
        gold_shares, token_shares = [], []
        outside = 0
        for _, r in sub.iterrows():
            gs, ts = convergence_shares(r["D"], r["Gap_15"], r[col])
            if np.isnan(gs):
                continue
            gold_shares.append(gs)
            token_shares.append(ts)
            if gs < 0 or gs > 1 or ts < 0 or ts > 1:
                outside += 1
        out[f"gold_share_{hours}h_mean"] = float(np.nanmean(gold_shares)) if gold_shares else np.nan
        out[f"token_share_{hours}h_mean"] = float(np.nanmean(token_shares)) if token_shares else np.nan
        out[f"gold_share_{hours}h_median"] = float(np.nanmedian(gold_shares)) if gold_shares else np.nan
        out[f"token_share_{hours}h_median"] = float(np.nanmedian(token_shares)) if token_shares else np.nan
        # Pooled: sum(Gap)/sum(D) and -sum(R)/sum(D)
        d_sum = float(sub["D"].sum())
        if abs(d_sum) > 1e-12:
            out[f"gold_share_{hours}h_pooled"] = float(sub["Gap_15"].sum() / d_sum)
            out[f"token_share_{hours}h_pooled"] = float(-sub[col].sum() / d_sum)
        else:
            out[f"gold_share_{hours}h_pooled"] = np.nan
            out[f"token_share_{hours}h_pooled"] = np.nan
        out[f"n_{hours}h"] = len(gold_shares)
        out[f"outside_unit_interval_{hours}h"] = outside

    # % of weekends where |gap| (excess basis) shrank >50% within 4h
    # Approximate remaining dislocation after 4h as D + Gap_15 + R_4h? 
    # Remaining ≈ (T_post/G_open - 1 - B) but we use |D + Gap contribution and token|:
    # simpler: |D| closed if |D + (-token_share*D approx)| — use |T path|:
    # closed_frac = 1 - |D + Gap_15 wait|
    # Spec: |gap| shrank by >50% within 4h — use |D| vs residual after gold+token moves
    # residual ≈ D - Gap_15 + R_4h  (gold moving Gap reduces D in same sign space when Gap≈D direction)
    if len(sub):
        residual = sub["D"] - sub["Gap_15"] + sub["R_4h"]
        shrunk = (residual.abs() < 0.5 * sub["D"].abs()) & sub["D"].notna()
        out["pct_shrunk_50pct_4h"] = float(shrunk.mean())
        # Who did the shrinking: |Gap| > |R| → gold, else token
        gold_led = shrunk & (sub["Gap_15"].abs() >= sub["R_4h"].abs())
        tok_led = shrunk & (sub["R_4h"].abs() > sub["Gap_15"].abs())
        out["pct_shrunk_gold_led"] = float(gold_led.mean()) if len(sub) else np.nan
        out["pct_shrunk_token_led"] = float(tok_led.mean()) if len(sub) else np.nan
        out["n_shrunk"] = int(shrunk.sum())
    else:
        out["pct_shrunk_50pct_4h"] = np.nan
        out["pct_shrunk_gold_led"] = np.nan
        out["pct_shrunk_token_led"] = np.nan
        out["n_shrunk"] = 0
    return out


def q4_subgroups(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    min_n = int(cfg["min_subgroup_n"])
    rows = []
    provisional = bool(df.get("label_provisional", pd.Series(dtype=bool)).astype(bool).any()) if "label_provisional" in df.columns else True

    def add(name: str, mask: pd.Series, note: str = ""):
        sub = df.loc[mask]
        n = len(sub)
        thin = n < min_n
        q2 = q2_follow(sub, cfg) if n else None
        q3 = q3_who_closes(sub, cfg) if n else None
        rows.append(
            {
                "group": name,
                "n": n,
                "too_thin": thin,
                "provisional": provisional and name in ("news", "quiet"),
                "note": note,
                "hit_rate": q2["hit_rate"]["hit_rate"] if q2 else np.nan,
                "hit_lo": q2["hit_rate"]["lo"] if q2 else np.nan,
                "hit_hi": q2["hit_rate"]["hi"] if q2 else np.nan,
                "slope": q2["slope"]["slope"] if q2 else np.nan,
                "slope_lo": q2["slope"]["lo"] if q2 else np.nan,
                "slope_hi": q2["slope"]["hi"] if q2 else np.nan,
                "token_share_1h_median": q3.get("token_share_1h_median", np.nan) if q3 else np.nan,
                "gold_share_1h_median": q3.get("gold_share_1h_median", np.nan) if q3 else np.nan,
            }
        )

    add("all", pd.Series(True, index=df.index))
    add("news", df["label"] == "news", note="PROVISIONAL until events.csv hand-confirmed")
    add("quiet", df["label"] == "quiet", note="PROVISIONAL until events.csv hand-confirmed")
    add("unknown_label", df["label"] == "unknown")
    add("crypto_crash", df["crypto_crash"].astype(bool))
    add("pre_2026", df["regime"] == "pre_2026")
    add("post_2026", df["regime"] == "post_2026")
    return pd.DataFrame(rows)


def q5_top_dislocations(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    sub = df.dropna(subset=["D"]).copy()
    sub["abs_D"] = sub["D"].abs()
    top = sub.nlargest(n, "abs_D")
    cols = [
        "friday_date", "token", "venue", "D", "W", "Gap_15", "R_1h", "R_4h",
        "label", "catalyst", "source_url", "crypto_crash",
    ]
    return top[[c for c in cols if c in top.columns]]


def honesty_checks(panel: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """Pre-registered robustness checks."""
    base = study_filter(panel)
    weekend = _weekend_level(base)
    out: dict[str, Any] = {}

    # By token
    for tok in sorted(base["token"].unique()):
        sub = _weekend_level(base.loc[base["token"] == tok])
        out[f"q2_token_{tok}"] = q2_follow(sub, cfg)

    # By venue (need ≥2 venues)
    venue_results = {}
    for ven in sorted(base["venue"].unique()):
        sub = _weekend_level(base.loc[base["venue"] == ven])
        if len(sub) >= 5:
            venue_results[ven] = q2_follow(sub, cfg)
    out["q2_by_venue"] = venue_results

    # Drop known case Fridays
    known = set(str(x) for x in cfg.get("known_case_fridays", []))
    dropped = weekend.loc[~weekend["friday_date"].astype(str).isin(known)]
    out["q2_drop_known_cases"] = q2_follow(dropped, cfg)
    out["n_known_cases_in_sample"] = int(weekend["friday_date"].astype(str).isin(known).sum())

    # Partial-weekend signal (Fri→Sat noon) — NOT a placebo; renamed in v2
    if "W_partial_sat_noon" in weekend.columns:
        w = weekend["W_partial_sat_noon"].values.astype(float)
        gap = weekend["Gap_15"].values.astype(float)
        out["partial_weekend_sat_noon"] = {
            "hit_rate": hit_rate_and_ci(w, gap, cfg["bootstrap_samples"], cfg["bootstrap_seed"]),
            "slope": slope_and_ci(w, gap, cfg["bootstrap_samples"], cfg["bootstrap_seed"]),
            "note": "Fri→Sat noon token move vs Sunday Gap_15 (part of the real weekend).",
        }

    # Real placebo 1: shuffled pairing (10k permutations)
    w = weekend["W"].values.astype(float)
    gap = weekend["Gap_15"].values.astype(float)
    mask = ~(np.isnan(w) | np.isnan(gap) | (w == 0) | (gap == 0))
    w_m, gap_m = w[mask], gap[mask]
    if len(w_m) >= 5:
        rng = np.random.default_rng(cfg["bootstrap_seed"])
        real_hr = float(np.mean([same_sign(a, b) for a, b in zip(w_m, gap_m)]))
        null_hrs = []
        n_perm = int(cfg["bootstrap_samples"])
        for _ in range(n_perm):
            shuffled = rng.permutation(gap_m)
            null_hrs.append(float(np.mean([same_sign(a, b) for a, b in zip(w_m, shuffled)])))
        n_ge = int(np.sum(np.array(null_hrs) >= real_hr))
        # One-sided Monte Carlo p; if zero hits, report p < 1/(n_perm+1)
        p_raw = (n_ge + 1) / (n_perm + 1)
        out["placebo_shuffled"] = {
            "real_hit_rate": real_hr,
            "null_mean": float(np.mean(null_hrs)),
            "null_lo": float(np.percentile(null_hrs, 2.5)),
            "null_hi": float(np.percentile(null_hrs, 97.5)),
            "pct_null_ge_real": float(n_ge / n_perm),
            "n_null_ge_real": n_ge,
            "n_perm": n_perm,
            "p": p_raw,
            "p_report": f"p < 1/{n_perm + 1}" if n_ge == 0 else f"p = {p_raw:.4f}",
            "n": int(len(w_m)),
            "note": "EXPLORATORY v2: pair each weekend's W with another weekend's Gap.",
        }

    # Real placebo 2: weekday token move (Thu 17→Fri 16) vs Sunday gap
    if "W_weekday_placebo" in weekend.columns:
        ww = weekend["W_weekday_placebo"].values.astype(float)
        out["placebo_weekday"] = {
            "hit_rate": hit_rate_and_ci(ww, gap, cfg["bootstrap_samples"], cfg["bootstrap_seed"]),
            "note": "EXPLORATORY v2: Thu 17:00→Fri 16:00 token move vs Sunday Gap (gold was open).",
        }

    # Stale drop counts
    if "excluded_reason" in panel.columns:
        stale = panel.loc[panel["excluded_reason"] == "stale_snapshot"]
        out["stale_dropped_by_venue"] = stale.groupby("venue").size().to_dict() if len(stale) else {}
        out["n_stale_dropped"] = int(len(stale))

    # Gap_15 vs GC=F
    if "Gap_15_gcf" in weekend.columns:
        mask = weekend["Gap_15"].notna() & weekend["Gap_15_gcf"].notna()
        if mask.sum() >= 5:
            agree = (
                np.sign(weekend.loc[mask, "Gap_15"]) == np.sign(weekend.loc[mask, "Gap_15_gcf"])
            ).mean()
            out["gcf_sign_agreement"] = float(agree)
            out["gcf_n"] = int(mask.sum())

    # Sensitivity k=5,60
    out["q2_gap5"] = q2_follow(weekend, cfg, gap_col="Gap_5")
    out["q2_gap60"] = q2_follow(weekend, cfg, gap_col="Gap_60")

    # Point-price sensitivity (old single-minute definition)
    if "W_point" in weekend.columns:
        wp = weekend["W_point"].values.astype(float)
        out["q2_point_price_sensitivity"] = {
            "hit_rate": hit_rate_and_ci(wp, gap, cfg["bootstrap_samples"], cfg["bootstrap_seed"]),
            "note": "EXPLORATORY sensitivity: single-minute point prices instead of ±5min median.",
        }

    # Labels: GDELT vs confirmed agreement
    confirmed = base.loc[base["label_confirmed"].isin(["news", "quiet"])] if "label_confirmed" in base.columns else base.iloc[0:0]
    if len(confirmed):
        agree = (confirmed["label_confirmed"] == confirmed["label_suggested"]).mean()
        out["gdelt_label_agreement"] = float(agree)
        out["gdelt_label_n"] = int(len(confirmed))
    else:
        out["gdelt_label_agreement"] = np.nan
        out["gdelt_label_n"] = 0
        out["labels_pending_confirmation"] = True
        out["labels_note"] = "All news/quiet splits are PROVISIONAL until events.csv is hand-confirmed."

    return out


def event_study_basis_path(
    cfg: dict[str, Any],
    cleaned: dict[str, Any],
    panel: pd.DataFrame,
) -> pd.DataFrame:
    """Mean token-vs-gold basis from Fri close −0h through Mon +0 relative to reopen.

    Simplified: sample every 15 minutes Fri close → Mon 17:00 ET equivalent window.
    """
    from src.calendar import friday_close_utc, post_open_utc

    base = study_filter(panel)
    # Use one primary series: prefer okx PAXG, else first available
    preferred = None
    for key in cleaned["token_usd"]:
        if "okx" in key.lower() and "PAXG" in key:
            preferred = key
            break
    if preferred is None and cleaned["token_usd"]:
        preferred = next(iter(cleaned["token_usd"]))
    if preferred is None:
        return pd.DataFrame()

    token = cleaned["token_usd"][preferred]
    gold = cleaned["gold_usd"]
    # Collect per-weekend basis paths aligned by minutes from Friday close
    paths = []
    fridays = base["friday_date"].unique()
    for fri_s in fridays:
        fri = pd.Timestamp(fri_s).date()
        # weekday basis for this weekend from panel
        b = base.loc[base["friday_date"].astype(str) == str(fri_s), "B_weekday"]
        b_weekday = float(b.mean()) if len(b) else 0.0
        t0 = pd.Timestamp(friday_close_utc(fri, cfg))
        # 15-min steps for ~3.5 days
        times = pd.date_range(t0, t0 + pd.Timedelta(hours=72), freq="15min", tz="UTC")
        series = []
        for ts in times:
            tp = price_at_safe(token, ts)
            gp = price_at_safe(gold, ts)
            if np.isnan(tp) or np.isnan(gp) or gp == 0:
                series.append(np.nan)
            else:
                series.append(tp / gp - 1.0 - b_weekday)
        paths.append(pd.Series(series, index=(times - t0).total_seconds() / 3600.0))

    if not paths:
        return pd.DataFrame()
    mat = pd.concat(paths, axis=1)
    out = pd.DataFrame(
        {
            "hours_from_fri_close": mat.index,
            "mean_basis": mat.mean(axis=1),
            "lo": mat.quantile(0.025, axis=1),
            "hi": mat.quantile(0.975, axis=1),
            "n": mat.notna().sum(axis=1),
        }
    )
    return out


def price_at_safe(series: pd.Series, ts) -> float:
    from src.math_defs import price_at

    return price_at(series, pd.Timestamp(ts), tolerance_min=2)


def run_analysis(cfg: dict[str, Any], panel: pd.DataFrame, cleaned: dict[str, Any] | None = None) -> dict[str, Any]:
    logger = setup_logging()
    base = study_filter(panel)
    weekend = _weekend_level(base)
    logger.info("Analysis sample: %d venue-rows → %d weekends", len(base), len(weekend))

    honesty = honesty_checks(panel, cfg)
    venues_contributing = sorted(str(v) for v in base["venue"].dropna().unique())
    results = {
        "version": "v2.1",
        "n_venue_rows": int(len(base)),
        "n_weekends": int(len(weekend)),
        "n_dropped_coverage": int((panel["excluded_reason"] == "coverage_gt_5pct").sum()),
        "n_dropped_stale": int((panel["excluded_reason"] == "stale_snapshot").sum()),
        "n_holiday_rows": int(panel["holiday_weekend"].sum()),
        "venues_contributing": venues_contributing,
        "usd_fallback": (cleaned or {}).get("usd_fallback_stats"),
        "q1": q1_drift(weekend),
        "q2": q2_follow(weekend, cfg),
        "q3": q3_who_closes(weekend, cfg),
        "q4": q4_subgroups(weekend, cfg),
        "q5": q5_top_dislocations(base, 10),
        "honesty": honesty,
        "weekend_panel": weekend,
        "venue_panel": base,
    }
    if cleaned is not None:
        results["event_study"] = event_study_basis_path(cfg, cleaned, panel)

    # Holiday list vs CME/LBMA (v2.1)
    try:
        from src.holiday_verify import verify_holidays

        results["holiday_verification"] = verify_holidays(cfg)
        logger.info("Holiday verification:\n%s", results["holiday_verification"])
    except Exception as e:  # noqa: BLE001
        logger.warning("Holiday verification failed: %s", e)
        results["holiday_verification"] = f"(failed: {e})"

    # Exploratory extras (Parts B/C) — labeled in their own modules
    try:
        from src.exploratory import run_exploratory

        results["exploratory"] = run_exploratory(cfg, panel, cleaned)
    except Exception as e:  # noqa: BLE001
        logger.warning("Exploratory analyses failed: %s", e)
        results["exploratory"] = {"error": str(e)}

    cache = cfg["paths"]["processed"] / "analysis_cache.pkl"
    import pickle

    with open(cache, "wb") as f:
        pickle.dump(results, f)
    logger.info("Analysis cache → %s", cache)
    return results
