"""EXPLORATORY analyses added in v2 after seeing v1 results. Not preregistered."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.analysis import hit_rate_and_ci, q2_follow, q3_who_closes, slope_and_ci, study_filter, _weekend_level
from src.logging_utils import setup_logging
from src.math_defs import simple_return


def magnitude_buckets(weekend: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Hit rate / slope by |W| bucket (Wilson CIs). EXPLORATORY."""
    bins = [0, 0.0025, 0.005, 0.01, 10]
    labels = ["<0.25%", "0.25–0.5%", "0.5–1%", ">1%"]
    df = weekend.dropna(subset=["W", "Gap_15"]).copy()
    df["abs_W"] = df["W"].abs()
    df["bucket"] = pd.cut(df["abs_W"], bins=bins, labels=labels, right=True)
    rows = []
    for lab in labels:
        sub = df.loc[df["bucket"] == lab]
        q2 = q2_follow(sub, cfg) if len(sub) else None
        rows.append(
            {
                "bucket": lab,
                "n": int(len(sub)),
                "hit_rate": q2["hit_rate"]["hit_rate"] if q2 else np.nan,
                "hit_lo": q2["hit_rate"]["lo"] if q2 else np.nan,
                "hit_hi": q2["hit_rate"]["hi"] if q2 else np.nan,
                "ci_method": "wilson",
                "slope": q2["slope"]["slope"] if q2 else np.nan,
                "exploratory": True,
            }
        )
    # Combined >0.5% bucket (v2.1)
    big = df.loc[df["abs_W"] > 0.005]
    q2b = q2_follow(big, cfg) if len(big) else None
    rows.append(
        {
            "bucket": ">0.5% (combined)",
            "n": int(len(big)),
            "hit_rate": q2b["hit_rate"]["hit_rate"] if q2b else np.nan,
            "hit_lo": q2b["hit_rate"]["lo"] if q2b else np.nan,
            "hit_hi": q2b["hit_rate"]["hi"] if q2b else np.nan,
            "ci_method": "wilson",
            "slope": q2b["slope"]["slope"] if q2b else np.nan,
            "exploratory": True,
        }
    )
    return pd.DataFrame(rows)


def up_down_asymmetry(weekend: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """EXPLORATORY: hit rate for W<0 vs W>0, plus bootstrap CI on the difference."""
    down = weekend.loc[weekend["W"] < 0]
    up = weekend.loc[weekend["W"] > 0]
    d = q2_follow(down, cfg)
    u = q2_follow(up, cfg)
    # Bootstrap CI for hit_up - hit_down
    rng = np.random.default_rng(cfg["bootstrap_seed"])
    diffs = []
    w_all = weekend["W"].values.astype(float)
    g_all = weekend["Gap_15"].values.astype(float)
    for _ in range(cfg["bootstrap_samples"]):
        idx = rng.integers(0, len(weekend), size=len(weekend))
        ww, gg = w_all[idx], g_all[idx]
        up_m = (ww > 0) & (ww != 0) & (gg != 0) & ~np.isnan(ww) & ~np.isnan(gg)
        dn_m = (ww < 0) & (ww != 0) & (gg != 0) & ~np.isnan(ww) & ~np.isnan(gg)
        if up_m.sum() == 0 or dn_m.sum() == 0:
            continue
        hu = np.mean(np.sign(ww[up_m]) == np.sign(gg[up_m]))
        hd = np.mean(np.sign(ww[dn_m]) == np.sign(gg[dn_m]))
        diffs.append(hu - hd)
    diff_point = (
        (u["hit_rate"]["hit_rate"] - d["hit_rate"]["hit_rate"])
        if u and d and not np.isnan(u["hit_rate"]["hit_rate"]) and not np.isnan(d["hit_rate"]["hit_rate"])
        else np.nan
    )
    return {
        "down": d,
        "up": u,
        "n_down": int(len(down)),
        "n_up": int(len(up)),
        "hit_up_minus_down": diff_point,
        "hit_up_minus_down_lo": float(np.percentile(diffs, 2.5)) if diffs else np.nan,
        "hit_up_minus_down_hi": float(np.percentile(diffs, 97.5)) if diffs else np.nan,
        "exploratory": True,
        "note": "Thesis is about down moves; compare carefully. Diff CI is bootstrap.",
    }


def venue_informativeness(panel: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Paired comparison of venues on shared weekends. EXPLORATORY."""
    base = study_filter(panel)
    # Pivot W by venue for PAXG where possible
    rows = []
    for ven in sorted(base["venue"].unique()):
        sub = _weekend_level(base.loc[base["venue"] == ven])
        q2 = q2_follow(sub, cfg)
        rows.append({"venue": ven, "n": len(sub), **{f"hit_{k}": v for k, v in q2["hit_rate"].items()}, "slope": q2["slope"]["slope"]})
    # Bootstrap difference OKX vs Binance if both present
    out = {"by_venue": pd.DataFrame(rows), "exploratory": True}
    okx = base.loc[base["venue"] == "okx"]
    bn = base.loc[base["venue"] == "binance"]
    shared = set(okx["weekend_id"]) & set(bn["weekend_id"])
    if len(shared) >= 10:
        o = okx.loc[okx["weekend_id"].isin(shared)].groupby("weekend_id", as_index=False)[["W", "Gap_15"]].mean()
        b = bn.loc[bn["weekend_id"].isin(shared)].groupby("weekend_id", as_index=False)[["W", "Gap_15"]].mean()
        merged = o.merge(b, on="weekend_id", suffixes=("_okx", "_bn"))
        # Compare |corr| via hit rates
        hr_o = hit_rate_and_ci(merged["W_okx"].values, merged["Gap_15_okx"].values, cfg["bootstrap_samples"], cfg["bootstrap_seed"])
        hr_b = hit_rate_and_ci(merged["W_bn"].values, merged["Gap_15_bn"].values, cfg["bootstrap_samples"], cfg["bootstrap_seed"])
        rng = np.random.default_rng(cfg["bootstrap_seed"])
        diffs = []
        for _ in range(cfg["bootstrap_samples"]):
            idx = rng.integers(0, len(merged), size=len(merged))
            s = merged.iloc[idx]
            ho = np.mean(np.sign(s["W_okx"]) == np.sign(s["Gap_15_okx"]))
            hb = np.mean(np.sign(s["W_bn"]) == np.sign(s["Gap_15_bn"]))
            # careful with zeros
            diffs.append(ho - hb)
        out["okx_minus_binance_hit"] = {
            "point": hr_o["hit_rate"] - hr_b["hit_rate"],
            "lo": float(np.percentile(diffs, 2.5)),
            "hi": float(np.percentile(diffs, 97.5)),
            "n_shared": int(len(merged)),
        }
    return out


def time_of_information(weekend: pd.DataFrame) -> pd.DataFrame:
    """Share of full weekend move completed by Sat noon / Sun 00 / Sun 12. EXPLORATORY."""
    rows = []
    for label in ["all", "news", "quiet"]:
        sub = weekend if label == "all" else weekend.loc[weekend["label"] == label]
        for col, name in [("W_partial_sat_noon", "sat_noon"), ("W_sun_00", "sun_00"), ("W_sun_12", "sun_12")]:
            if col not in sub.columns:
                continue
            ratio = (sub[col] / sub["W"]).replace([np.inf, -np.inf], np.nan)
            # only where W != 0
            ratio = ratio.loc[sub["W"].abs() > 1e-8]
            rows.append(
                {
                    "group": label,
                    "checkpoint": name,
                    "median_share_of_W": float(ratio.median()) if len(ratio) else np.nan,
                    "mean_share_of_W": float(ratio.mean()) if len(ratio) else np.nan,
                    "n": int(len(ratio)),
                    "provisional": label in ("news", "quiet"),
                    "exploratory": True,
                }
            )
    return pd.DataFrame(rows)


def regime_rolling_slope(weekend: pd.DataFrame, window: int = 26) -> pd.DataFrame:
    """26-weekend rolling slope of Gap~W. EXPLORATORY."""
    df = weekend.dropna(subset=["W", "Gap_15"]).sort_values("friday_date").reset_index(drop=True)
    rows = []
    for i in range(window - 1, len(df)):
        sub = df.iloc[i - window + 1 : i + 1]
        x, y = sub["W"].values, sub["Gap_15"].values
        if len(x) < 5:
            continue
        X = np.column_stack([np.ones(len(x)), x])
        coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        rows.append({"friday_date": sub["friday_date"].iloc[-1], "rolling_slope": float(coef[1]), "n": window})
    return pd.DataFrame(rows)


def gap_fill(weekend: pd.DataFrame) -> dict[str, Any]:
    """How often gold returns to Friday close by Mon 17:00. EXPLORATORY."""
    if "G_mon_17et" not in weekend.columns or "G_fri" not in weekend.columns:
        return {"error": "missing Monday gold columns"}
    df = weekend.dropna(subset=["G_fri", "G_open_15", "G_mon_17et", "W"]).copy()
    # Gap filled if Mon close is closer to Fri than the reopen was
    gap = df["G_open_15"] / df["G_fri"] - 1
    mon = df["G_mon_17et"] / df["G_fri"] - 1
    filled = mon.abs() < gap.abs() * 0.5  # at least half filled toward Friday
    signaled = np.sign(df["W"]) == np.sign(gap)
    return {
        "pct_half_filled_all": float(filled.mean()) if len(df) else np.nan,
        "pct_half_filled_pre_signaled": float(filled.loc[signaled].mean()) if signaled.any() else np.nan,
        "pct_half_filled_not_signaled": float(filled.loc[~signaled].mean()) if (~signaled).any() else np.nan,
        "n": int(len(df)),
        "exploratory": True,
    }


def holiday_q2q3(panel: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """Q2/Q3 on holiday weekends only. EXPLORATORY."""
    hol = panel.loc[panel["holiday_weekend"].astype(bool) & panel["study_sample"].astype(bool)].copy()
    # include even if excluded_main for holiday reason, but still require coverage
    hol = hol.loc[hol["excluded_reason"].isin(["", "holiday_weekend"]) | hol["excluded_reason"].isna()]
    hol = hol.loc[hol["pct_missing_weekend_minutes"] <= cfg["coverage_drop_threshold"]]
    if "stale_any" in hol.columns:
        hol = hol.loc[~hol["stale_any"].astype(bool)]
    weekend = _weekend_level(hol)
    return {
        "n_weekends": int(len(weekend)),
        "q2": q2_follow(weekend, cfg) if len(weekend) else None,
        "q3": q3_who_closes(weekend, cfg) if len(weekend) else None,
        "exploratory": True,
        "note": "Expect noisier; show N.",
    }


def manipulation_links(panel: pd.DataFrame, cfg: dict[str, Any], cleaned: dict | None) -> dict[str, Any]:
    """Four-link manipulation thesis test. EXPLORATORY. No wallet accusations."""
    logger = setup_logging()
    base = study_filter(panel)
    # Link 1: candidate dislocations
    cand = base.loc[
        (base["D"].abs() > 0.01)
        & (base["label"] == "quiet")
        & (~base.get("stale_any", False) if "stale_any" in base.columns else True)
    ].copy()
    # Prefer confirmed quiet; mark provisional
    cand["provisional"] = cand.get("label_provisional", True)

    # Cross-venue agreement per weekend
    market_wide = []
    single = []
    for wid, g in cand.groupby("weekend_id"):
        moves = g[["venue", "token", "D", "W"]].copy()
        # compare D across venues
        if len(g) >= 2:
            vals = g["D"].values
            if np.nanmax(vals) - np.nanmin(vals) <= 0.005 and np.all(np.sign(vals) == np.sign(vals[0])):
                market_wide.append(wid)
            else:
                # check pairwise within 0.5%
                agree = False
                for i in range(len(vals)):
                    for j in range(i + 1, len(vals)):
                        if abs(vals[i] - vals[j]) <= 0.005 and np.sign(vals[i]) == np.sign(vals[j]):
                            agree = True
                (market_wide if agree else single).append(wid)
        else:
            single.append(wid)

    link1 = {
        "n_candidate_rows": int(len(cand)),
        "n_candidate_weekends": int(cand["weekend_id"].nunique()),
        "by_venue_token": cand.groupby(["venue", "token"]).size().to_dict(),
        "n_market_wide": len(market_wide),
        "n_single_venue": len(single),
        "provisional_labels": True,
        "exploratory": True,
    }

    # Link 2: transmission — gold share vs snap-back for |D|>1%
    def shares_for(ids):
        sub = cand.loc[cand["weekend_id"].isin(ids)]
        if sub.empty:
            return {}
        q3 = q3_who_closes(sub.assign(D=sub["D"]), {**cfg, "dislocation_threshold": 0.01})
        return {
            "gold_share_4h_median": q3.get("gold_share_4h_median"),
            "token_share_4h_median": q3.get("token_share_4h_median"),
            "gold_share_4h_pooled": q3.get("gold_share_4h_pooled"),
            "token_share_4h_pooled": q3.get("token_share_4h_pooled"),
            "n": int(len(sub)),
        }

    link2 = {
        "all_candidates": shares_for(cand["weekend_id"].unique()),
        "market_wide": shares_for(market_wide),
        "single_venue": shares_for(single),
        "by_venue": {},
        "exploratory": True,
        "note": "Thesis needs high gold share on quiet token-led moves.",
    }
    for ven in cand["venue"].unique():
        link2["by_venue"][ven] = shares_for(cand.loc[cand["venue"] == ven, "weekend_id"])

    # Link 3: post-open gold drift
    def gold_drift(sub: pd.DataFrame) -> dict:
        if sub.empty or "G_open_15" not in sub.columns:
            return {"n": 0}
        g0 = sub["G_open_15"]
        out = {"n": int(len(sub))}
        for col, name in [("G_mon_03et", "to_mon_03et"), ("G_mon_0530et", "to_lbma_am_approx"), ("G_mon_17et", "to_mon_17et")]:
            if col not in sub.columns:
                continue
            ret = (sub[col] / g0 - 1).dropna()
            if len(ret) == 0:
                out[name] = {}
                continue
            point, lo, hi = _boot_mean(ret.values, cfg)
            out[name] = {"mean": point, "lo": lo, "hi": hi, "n": int(len(ret))}
        return out

    quiet_down = base.loc[(base["label"] == "quiet") & (base["W"] < -0.0025)]
    news_down = base.loc[(base["label"] == "news") & (base["W"] < -0.0025)]
    other = base.loc[~base.index.isin(quiet_down.index) & ~base.index.isin(news_down.index)]
    quiet_up = base.loc[(base["label"] == "quiet") & (base["W"] > 0.0025)]

    link3 = {
        "after_quiet_token_down": gold_drift(_weekend_level(quiet_down) if len(quiet_down) else quiet_down),
        "after_news_token_down": gold_drift(_weekend_level(news_down) if len(news_down) else news_down),
        "after_other": gold_drift(_weekend_level(other) if len(other) else other),
        "after_quiet_token_up_symmetry": gold_drift(_weekend_level(quiet_up) if len(quiet_up) else quiet_up),
        "provisional_labels": True,
        "exploratory": True,
        "note": "Efficient-market null: mean post-open drift ≈ 0 for all groups.",
    }

    # Link 4: on-chain — attempt free data; often untestable without API key
    link4 = run_onchain_candidates(cand, base, cfg)

    # Verdicts
    def verdict_link2():
        gs = link2["all_candidates"].get("gold_share_4h_median")
        ts = link2["all_candidates"].get("token_share_4h_median")
        if gs is None or (isinstance(gs, float) and np.isnan(gs)):
            return "untestable", "no candidate weekends after filters"
        if gs > 0.5 and (ts is None or ts < gs):
            return "supported", f"median gold share={gs:.2f} > token snap-back"
        return "not supported", f"median gold share={gs:.2f}, token share={ts}"

    def verdict_link3():
        d = link3["after_quiet_token_down"].get("to_mon_17et", {})
        if not d or d.get("n", 0) < 5:
            return "untestable", "too few quiet-down weekends"
        # Support thesis if significant positive recovery after down opens
        if d.get("lo", -1) > 0:
            return "supported", f"Mon 17:00 drift mean={d.get('mean'):.4f} CI excludes 0"
        if d.get("hi", 1) < 0:
            return "not supported", f"continued decline mean={d.get('mean'):.4f}"
        return "not supported", f"drift CI includes 0 (mean={d.get('mean')})"

    n_confirmed = int(base["label_confirmed"].isin(["news", "quiet"]).sum()) if "label_confirmed" in base.columns else 0
    pending = ("pending labels", "n confirmed labels = 0 — confirm events.csv before judging Links 1–4")
    if n_confirmed == 0:
        # v2.1: do not call Links “not supported” when labels are unconfirmed
        v1 = v2 = v3 = v4 = pending
    else:
        v1 = ("supported" if link1["n_candidate_weekends"] > 0 else "not supported", f"n={link1['n_candidate_weekends']}")
        v2 = verdict_link2()
        v3 = verdict_link3()
        v4 = link4.get("verdict", ("untestable", link4.get("note", "")))

    # Q3 pooled vs median per venue + leave-out 2025-01-31 (v2.1)
    weekend_lvl = _weekend_level(base)
    q3_venue = {}
    for ven in sorted(base["venue"].unique()):
        sub = base.loc[base["venue"] == ven]
        q3_venue[ven] = q3_who_closes(_weekend_level(sub) if len(sub) else sub, cfg)
    without_jan31 = base.loc[base["friday_date"].astype(str) != "2025-01-31"]
    q3_sensitivity = {
        "all": q3_who_closes(weekend_lvl, cfg),
        "per_venue": q3_venue,
        "without_2025_01_31": q3_who_closes(_weekend_level(without_jan31), cfg),
        "exploratory": True,
    }

    def _status_detail(x):
        if isinstance(x, tuple):
            return {"status": x[0], "detail": x[1]}
        return {"status": str(x), "detail": ""}

    return {
        "link1": link1,
        "link2": link2,
        "link3": link3,
        "link4": link4,
        "q3_venue_sensitivity": q3_sensitivity,
        "n_confirmed_labels": n_confirmed,
        "verdict": {
            "link1_tokens_move_without_news": _status_detail(v1),
            "link2_transmits_to_gold": _status_detail(v2),
            "link3_gold_opens_below_fair": _status_detail(v3),
            "link4_onchain_flows": _status_detail(v4),
        },
        "exploratory": True,
    }


def _boot_mean(vals: np.ndarray, cfg: dict) -> tuple[float, float, float]:
    vals = np.asarray(vals, dtype=float)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(cfg["bootstrap_seed"])
    boots = [float(np.mean(rng.choice(vals, size=len(vals), replace=True))) for _ in range(cfg["bootstrap_samples"])]
    return float(np.mean(vals)), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def run_onchain_candidates(cand: pd.DataFrame, base: pd.DataFrame, cfg: dict) -> dict[str, Any]:
    """Try free Ethereum logs for PAXG/XAUT transfers. EXPLORATORY. No named attributions."""
    logger = setup_logging()
    # Official contract addresses (verify on issuer sites / Etherscan):
    # PAXG: https://etherscan.io/token/0x45804880De22913dAFE09f4980848ECE6EcbAf78
    # XAUT: https://etherscan.io/token/0x68749665FF8D2d112Fa859AA293F07A622782F38
    contracts = {
        "PAXG": "0x45804880De22913dAFE09f4980848ECE6EcbAf78",
        "XAUT": "0x68749665FF8D2d112Fa859AA293F07A622782F38",
    }
    n_cand = int(cand["weekend_id"].nunique())
    if n_cand == 0:
        return {
            "verdict": ("untestable", "no candidate weekends"),
            "note": "No quiet |D|>1% candidates after Part A filters.",
            "exploratory": True,
        }

    # Public RPC eth_getLogs often rate-limits; attempt one lightweight check then document.
    import requests

    rpc = "https://ethereum.publicnode.com"
    try:
        # Just verify contracts have code (connectivity check)
        r = requests.post(
            rpc,
            json={"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [contracts["PAXG"], "latest"]},
            timeout=20,
        )
        code_ok = len((r.json() or {}).get("result") or "0x") > 4
    except Exception as e:  # noqa: BLE001
        logger.warning("On-chain RPC check failed: %s", e)
        code_ok = False

    return {
        "verdict": (
            "untestable",
            "Full Transfer+label analysis needs indexed archive (Etherscan API key / The Graph). "
            "Contracts verified reachable." if code_ok else "RPC unreachable; not run.",
        ),
        "contracts_cited": contracts,
        "n_candidate_weekends": n_cand,
        "n_control_planned": n_cand,
        "exploratory": True,
        "note": (
            "Descriptive only if run later. Refer to wallets as A/B — never name owners or firms. "
            "Sources for labels must be cited per address."
        ),
    }


def run_exploratory(cfg: dict[str, Any], panel: pd.DataFrame, cleaned: dict | None) -> dict[str, Any]:
    logger = setup_logging()
    base = study_filter(panel)
    weekend = _weekend_level(base)
    logger.info("Running EXPLORATORY analyses on %d weekends", len(weekend))

    out = {
        "magnitude_buckets": magnitude_buckets(weekend, cfg),
        "up_down": up_down_asymmetry(weekend, cfg),
        "venue_informativeness": venue_informativeness(panel, cfg),
        "time_of_information": time_of_information(weekend),
        "regime_rolling_slope": regime_rolling_slope(weekend),
        "gap_fill": gap_fill(weekend),
        "holiday": holiday_q2q3(panel, cfg),
        "manipulation": manipulation_links(panel, cfg, cleaned),
    }

    # Robust regime check: drop 3 largest |W|, Huber if available
    df = weekend.dropna(subset=["W", "Gap_15"])
    if len(df) >= 10:
        trimmed = df.loc[df["W"].abs() < df["W"].abs().nlargest(3).min()]
        out["regime_drop3"] = {
            "pre_2026": q2_follow(trimmed.loc[trimmed["regime"] == "pre_2026"], cfg),
            "post_2026": q2_follow(trimmed.loc[trimmed["regime"] == "post_2026"], cfg),
            "exploratory": True,
        }
        try:
            from statsmodels.api import RLM
            import statsmodels.api as sm

            def huber_slope(sub):
                if len(sub) < 5:
                    return np.nan
                y = sub["Gap_15"].values
                X = sm.add_constant(sub["W"].values)
                return float(RLM(y, X).fit().params[1])

            out["regime_huber"] = {
                "pre_2026": huber_slope(df.loc[df["regime"] == "pre_2026"]),
                "post_2026": huber_slope(df.loc[df["regime"] == "post_2026"]),
                "exploratory": True,
            }
        except Exception as e:  # noqa: BLE001
            out["regime_huber"] = {"error": str(e)}

    return out
