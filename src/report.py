"""Write findings.md, charts, and manipulation_test.md from analysis results only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.logging_utils import setup_logging


def _venues_in_sample(results_or_cfg: dict[str, Any], cfg: dict[str, Any] | None = None) -> list[str]:
    """Venues that actually contribute study rows (not the full config list)."""
    cfg = cfg or results_or_cfg
    venues = results_or_cfg.get("venues_contributing") if isinstance(results_or_cfg, dict) else None
    if venues:
        return list(venues)
    # Fallback: only venues that appear in weekend_panel if present on cfg-like bag
    panel = results_or_cfg.get("weekend_panel") if isinstance(results_or_cfg, dict) else None
    if panel is not None and hasattr(panel, "columns") and "venue" in panel.columns:
        return sorted(str(v) for v in panel["venue"].dropna().unique())
    return []


def _source_footer(ax, cfg: dict[str, Any], venues: list[str] | None = None) -> None:
    end = cfg.get("study_end_date") or "latest complete weekend"
    venue_txt = ", ".join(v.title() if v != "okx" else "OKX" for v in (venues or []))
    if not venue_txt:
        venue_txt = "see findings for venues"
    # Always cite Dukascopy for gold spot; crypto venues from contributing rows only
    ax.figure.text(
        0.5,
        0.01,
        f"Data: Dukascopy + {venue_txt}. Jan 2025–{end}. Research only — not trading advice.",
        ha="center",
        fontsize=7,
        color="#555",
    )


def _pct(x: float, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{100 * x:.{digits}f}%"


def fig_q1_hist(q1: dict, cfg: dict, path: Path, venues: list[str] | None = None) -> None:
    vals = q1.get("values")
    if vals is None or len(vals) == 0:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(np.asarray(vals) * 100, bins=20, color="#2c5f4a", edgecolor="white")
    ax.axvline(q1["median"] * 100, color="#c45c26", lw=2, label=f"median {_pct(q1['median'])}")
    ax.set_xlabel("Weekend dislocation D (%)")
    ax.set_ylabel("Number of weekends")
    ax.set_title("Q1: How far do tokens drift from gold over the weekend?")
    ax.legend()
    _source_footer(ax, cfg, venues)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, dpi=140)
    plt.close(fig)


def fig_q2_scatter(weekend: pd.DataFrame, q2: dict, cfg: dict, path: Path, venues: list[str] | None = None) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {"news": "#c45c26", "quiet": "#2c5f4a", "crypto_crash": "#6b3fa0"}
    plotted = set()
    for _, r in weekend.iterrows():
        if np.isnan(r.get("W", np.nan)) or np.isnan(r.get("Gap_15", np.nan)):
            continue
        if r.get("crypto_crash"):
            c, lab = colors["crypto_crash"], "crypto-crash"
        else:
            raw = str(r.get("label") or "unknown")
            # Publish-facing: unconfirmed labels show as “unlabeled” (not “unknown”)
            if raw == "unknown":
                lab, c = "unlabeled", "#888"
            else:
                lab = raw
                c = colors.get(raw, "#888")
        if lab in plotted:
            ax.scatter(r["W"] * 100, r["Gap_15"] * 100, c=c, s=36, alpha=0.75)
        else:
            ax.scatter(r["W"] * 100, r["Gap_15"] * 100, c=c, s=36, alpha=0.75, label=lab)
            plotted.add(lab)
    lim = max(
        0.1,
        np.nanmax(np.abs(weekend["W"].values)) * 100 * 1.1 if len(weekend) else 0.5,
        np.nanmax(np.abs(weekend["Gap_15"].values)) * 100 * 1.1 if len(weekend) else 0.5,
    )
    xs = np.linspace(-lim, lim, 50)
    ax.plot(xs, xs, "--", color="#999", label="gold fully follows (45°)")
    sl = q2["slope"]
    if not np.isnan(sl["slope"]):
        ax.plot(xs, (sl["intercept"] + sl["slope"] * (xs / 100)) * 100, color="#1a1a1a", lw=2, label=f"fit slope={sl['slope']:.2f}")
    ax.set_xlabel("Weekend token move W (%)")
    ax.set_ylabel("Gold reopen gap Gap_15 (%)")
    ax.set_title("Q2: When tokens move over the weekend, does gold follow?")
    ax.legend(fontsize=8)
    ax.axhline(0, color="#ccc", lw=0.5)
    ax.axvline(0, color="#ccc", lw=0.5)
    _source_footer(ax, cfg, venues)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, dpi=140)
    plt.close(fig)


def fig_q3_stacked(q3: dict, cfg: dict, path: Path, venues: list[str] | None = None) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    labels = ["+1h median", "+4h median", "+4h pooled"]
    gold = [
        q3.get("gold_share_1h_median", np.nan),
        q3.get("gold_share_4h_median", np.nan),
        q3.get("gold_share_4h_pooled", np.nan),
    ]
    tok = [
        q3.get("token_share_1h_median", np.nan),
        q3.get("token_share_4h_median", np.nan),
        q3.get("token_share_4h_pooled", np.nan),
    ]
    gold_c = [np.clip(g, 0, 1) if not (g is None or np.isnan(g)) else 0 for g in gold]
    tok_c = [np.clip(t, 0, 1) if not (t is None or np.isnan(t)) else 0 for t in tok]
    ax.bar(labels, gold_c, label="gold moved", color="#c45c26")
    ax.bar(labels, tok_c, bottom=gold_c, label="token snapped back", color="#2c5f4a")
    ax.set_ylabel("Share of dislocation closed")
    ax.set_ylim(0, 1.15)
    ax.set_title(f"Q3 v2: Who closes large gaps? (|D|>{_pct(q3['threshold'])}, n={q3['n']})")
    ax.legend()
    note = "v2 uses median + pooled shares (means of ratios explode when D is small)."
    ax.text(0.5, -0.18, note, transform=ax.transAxes, ha="center", fontsize=7, color="#555")
    _source_footer(ax, cfg, venues)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(path, dpi=140)
    plt.close(fig)


def fig_q3_event_study(path_df: pd.DataFrame, cfg: dict, path: Path, venues: list[str] | None = None) -> None:
    if path_df is None or path_df.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.fill_between(path_df["hours_from_fri_close"], path_df["lo"] * 100, path_df["hi"] * 100, color="#2c5f4a", alpha=0.2, label="95% band")
    ax.plot(path_df["hours_from_fri_close"], path_df["mean_basis"] * 100, color="#2c5f4a", lw=2, label="mean excess basis")
    ax.axvline(48, color="#c45c26", ls="--", label="≈ Sunday reopen (+48h)")
    ax.axhline(0, color="#ccc", lw=0.8)
    ax.set_xlabel("Hours from Friday 17:00 ET close")
    ax.set_ylabel("Token − gold excess basis (%)")
    ax.set_title("Q3: Average token-vs-gold gap from Friday close through Monday")
    ax.legend(fontsize=8)
    _source_footer(ax, cfg, venues)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, dpi=140)
    plt.close(fig)


def fig_q2_by_magnitude(mag: pd.DataFrame, cfg: dict, path: Path, venues: list[str] | None = None) -> None:
    if mag is None or mag.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(mag))
    hr = mag["hit_rate"].astype(float).values * 100
    lo = mag["hit_lo"].astype(float).values * 100
    hi = mag["hit_hi"].astype(float).values * 100
    yerr = np.vstack([hr - lo, hi - hr])
    ax.bar(x, hr, color="#2c5f4a", yerr=yerr, capsize=4)
    ax.axhline(50, color="#999", ls="--", label="coin flip")
    ax.set_xticks(x)
    labels = [f"{b}\n(n={n})" for b, n in zip(mag["bucket"], mag["n"])]
    ax.set_xticklabels(labels)
    ax.set_ylabel("Same-sign hit rate (%)")
    ax.set_title("EXPLORATORY: Bigger weekend token moves → gold more often follows (Wilson 95% CI)")
    ax.set_ylim(0, 105)
    ax.legend()
    _source_footer(ax, cfg, venues)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(path, dpi=140)
    plt.close(fig)


def write_manipulation_md(cfg: dict[str, Any], manip: dict[str, Any]) -> None:
    v = manip.get("verdict", {})
    lines = [
        "# Manipulation thesis test (EXPLORATORY)",
        "",
        "Added in v2 after seeing results — **not preregistered**. News/quiet labels are **provisional** until `events.csv` is hand-confirmed.",
        "",
        "Thesis under test: *someone pushes weekend tokens to make gold look weaker, gold opens cheap, they buy the open.*",
        "All four links must hold. Failure of Link 2 or 3 means the profit mechanism does not operate, even if Link 1 holds.",
        "",
        "## Verdict",
        "",
        "| Link | Status | Detail |",
        "|------|--------|--------|",
    ]
    for key, label in [
        ("link1_tokens_move_without_news", "1 Tokens move without news"),
        ("link2_transmits_to_gold", "2 Move transmits to gold reopen"),
        ("link3_gold_opens_below_fair", "3 Gold opens below fair / recovers"),
        ("link4_onchain_flows", "4 On-chain flows"),
    ]:
        item = v.get(key, {})
        lines.append(f"| {label} | **{item.get('status', '?')}** | {item.get('detail', '')} |")
    lines += [
        "",
        "## Link details",
        "",
        f"- Link 1 candidates (|D|>1%, quiet, not stale): {manip.get('link1', {})}",
        f"- Link 2 shares: {manip.get('link2', {})}",
        f"- Link 3 post-open drift: {manip.get('link3', {})}",
        f"- Link 4: {manip.get('link4', {})}",
        "",
        "**No wallet owners or firms are named.** On-chain results, if added later, use wallet A/B only.",
        "",
    ]
    path = cfg["paths"]["reports"] / "manipulation_test.md"
    path.write_text("\n".join(lines), encoding="utf-8")


def write_findings(cfg: dict[str, Any], results: dict[str, Any]) -> str:
    q1, q2, q3 = results["q1"], results["q2"], results["q3"]
    q4: pd.DataFrame = results["q4"]
    q5: pd.DataFrame = results["q5"]
    hon = results["honesty"]
    hr = q2["hit_rate"]
    sl = q2["slope"]
    fb = results.get("usd_fallback") or {}
    expl = results.get("exploratory") or {}

    venues = results.get("venues_contributing") or []
    ci_note = "Wilson 95% CI" if hr.get("wilson_lo") is not None else "95% CI"
    tldr = [
        f"- **v2.1** sample: **{results['n_weekends']}** weekends ({results['n_venue_rows']} venue×token rows after coverage/holiday/**stale** filters). Venues: {', '.join(venues) or 'n/a'}.",
        f"- Weekend dislocation D median **{_pct(q1.get('median', float('nan')))}** (10th–90th: {_pct(q1.get('p10', float('nan')))} to {_pct(q1.get('p90', float('nan')))}).",
        f"- Same-sign hit rate: **{_pct(hr['hit_rate'], 1)}** ({ci_note} {_pct(hr['lo'], 1)}–{_pct(hr['hi'], 1)}); coin-flip = 50%.",
        f"- Slope: **{sl['slope']:.2f}** (CI {sl['lo']:.2f}–{sl['hi']:.2f}).",
        f"- Q3 (v2): median gold share +4h **{_pct(q3.get('gold_share_4h_median', float('nan')), 0)}**, "
        f"token **{_pct(q3.get('token_share_4h_median', float('nan')), 0)}**; "
        f"pooled gold **{_pct(q3.get('gold_share_4h_pooled', float('nan')), 0)}**.",
        "- News/quiet splits are **PROVISIONAL** (n confirmed labels = 0).",
    ]

    shuf = hon.get("placebo_shuffled", {})
    wk = hon.get("placebo_weekday", {})
    partial = hon.get("partial_weekend_sat_noon", {})

    lines = [
        "# Gold Weekend Study — Findings (v2.1)",
        "",
        f"_Generated from `weekends.parquet`. study_end_date = `{cfg.get('study_end_date')}`._",
        "",
        "## What changed from v1 → v2 → v2.1",
        "",
        "- Full-history USDT/USD via Bitstamp (Kraken ~720-bar cap fixed).",
        f"- USDT conversion rate=1.0 fallback now **{_pct(fb.get('pct_fallback_1', float('nan')), 2)}** of minutes (target <1%).",
        f"- Stale snapshots (>10 min since last trade) dropped: **{results.get('n_dropped_stale', 0)}** rows.",
        "- Snapshot prices = median of ±5 min closes (point prices kept as sensitivity).",
        "- Q3 uses **median + pooled** shares (not means of ratios).",
        "- Sat-noon renamed **partial-weekend signal**; real placebos = shuffled pairing + weekday move.",
        "- Failed GDELT → `unknown` (never silent `quiet`). New tests labeled **exploratory**.",
        "- **v2.1:** Binance = `data-api.binance.vision` only (no Binance.US mix); Wilson CIs; "
        "up−down bootstrap CI; Q3 per-venue / leave-out 2025-01-31; chart footers = contributing venues; "
        "Links 1–4 = pending labels when n confirmed = 0.",
        "",
        "## TL;DR",
        "",
        *tldr,
        "",
        "## Q1 — How far do the tokens drift?",
        "",
        f"**Answer:** Typical weekend dislocation ≈ {_pct(q1.get('median', float('nan')))} "
        f"(p10–p90 {_pct(q1.get('p10', float('nan')))} to {_pct(q1.get('p90', float('nan')))}); "
        f"largest absolute ≈ {_pct(q1.get('max', float('nan')))}.",
        "",
        f"- N weekends: {q1.get('n')} · Chart: `figures/q1_drift_hist.png`",
        "",
        "## Q2 — Does gold follow the token?",
        "",
        f"**Answer:** Same-sign hit rate **{_pct(hr['hit_rate'], 1)}** "
        f"(Wilson 95% CI {_pct(hr['lo'], 1)}–{_pct(hr['hi'], 1)}; n={hr['n']}"
        + (f", k={hr['k']}" if "k" in hr else "")
        + f"). Slope **{sl['slope']:.2f}** "
        f"(bootstrap CI {sl['lo']:.2f}–{sl['hi']:.2f}).",
        "",
        "- Chart: `figures/q2_scatter.png` · Headline exploratory chart: `figures/q2_hit_by_magnitude.png`",
        "",
        "## Q3 — Who closes the gap? (v2 method)",
        "",
        f"**Answer:** On |D|>0.25% (n={q3.get('n')}): median gold share +4h "
        f"{_pct(q3.get('gold_share_4h_median', float('nan')), 0)}, "
        f"token {_pct(q3.get('token_share_4h_median', float('nan')), 0)}; "
        f"pooled gold {_pct(q3.get('gold_share_4h_pooled', float('nan')), 0)}, "
        f"token {_pct(q3.get('token_share_4h_pooled', float('nan')), 0)}. "
        f"|gap| shrank >50% within 4h on {_pct(q3.get('pct_shrunk_50pct_4h', float('nan')), 0)} of those weekends "
        f"(gold-led {_pct(q3.get('pct_shrunk_gold_led', float('nan')), 0)}, "
        f"token-led {_pct(q3.get('pct_shrunk_token_led', float('nan')), 0)}).",
        "",
    ]

    # Q3 per-venue / leave-out sensitivity (v2.1)
    q3sens = (expl.get("manipulation") or {}).get("q3_venue_sensitivity") or expl.get("q3_venue_sensitivity")
    if q3sens:
        lines += ["### Q3 sensitivity (exploratory v2.1)", ""]
        for ven, v in (q3sens.get("per_venue") or {}).items():
            lines.append(
                f"- venue **{ven}** (n={v.get('n')}): median gold/token +4h "
                f"{_pct(v.get('gold_share_4h_median', float('nan')), 0)} / "
                f"{_pct(v.get('token_share_4h_median', float('nan')), 0)}; "
                f"pooled {_pct(v.get('gold_share_4h_pooled', float('nan')), 0)} / "
                f"{_pct(v.get('token_share_4h_pooled', float('nan')), 0)}"
            )
        w31 = q3sens.get("without_2025_01_31") or {}
        lines.append(
            f"- without 2025-01-31 (n={w31.get('n')}): median gold/token +4h "
            f"{_pct(w31.get('gold_share_4h_median', float('nan')), 0)} / "
            f"{_pct(w31.get('token_share_4h_median', float('nan')), 0)}; "
            f"pooled {_pct(w31.get('gold_share_4h_pooled', float('nan')), 0)} / "
            f"{_pct(w31.get('token_share_4h_pooled', float('nan')), 0)}"
        )
        lines.append("")

    lines += [
        "## Q4 — Weekend types (**provisional** news/quiet)",
        "",
        q4.to_markdown(index=False) if hasattr(q4, "to_markdown") else q4.to_string(index=False),
        "",
        "## Q5 — Top 10 dislocations",
        "",
        q5.to_markdown(index=False) if hasattr(q5, "to_markdown") else q5.to_string(index=False),
        "",
        "## Honesty checks / placebos",
        "",
        f"- Partial-weekend (Fri→Sat noon) hit rate: {_pct(partial.get('hit_rate', {}).get('hit_rate', float('nan')), 1)} — part of the real weekend, not a placebo.",
        f"- **Shuffled pairing placebo:** real hit {_pct(shuf.get('real_hit_rate', float('nan')), 1)}; "
        f"null mean {_pct(shuf.get('null_mean', float('nan')), 1)} "
        f"(CI {_pct(shuf.get('null_lo', float('nan')), 1)}–{_pct(shuf.get('null_hi', float('nan')), 1)}); "
        f"{shuf.get('p_report') or ('P(null≥real)=' + format(shuf.get('pct_null_ge_real', float('nan')), '.4f'))} "
        f"(n_null≥real={shuf.get('n_null_ge_real', '?')} / {shuf.get('n_perm', '?')}).",
        f"- **Weekday placebo** (Thu→Fri token vs Sunday gap): "
        f"{_pct(wk.get('hit_rate', {}).get('hit_rate', float('nan')), 1)}.",
        f"- Stale rows dropped: {hon.get('n_stale_dropped', results.get('n_dropped_stale'))} "
        f"by venue {hon.get('stale_dropped_by_venue', {})}.",
        f"- Drop known cases: hit {_pct(hon.get('q2_drop_known_cases', {}).get('hit_rate', {}).get('hit_rate', float('nan')), 1)}.",
        f"- GC=F sign agreement: {_pct(hon.get('gcf_sign_agreement', float('nan')), 0)} (n={hon.get('gcf_n', 'n/a')}).",
        f"- Confirmed labels: n={hon.get('gdelt_label_n', 0)} — news/quiet splits provisional.",
        "",
        "### By token / venue",
        "",
    ]
    for k, v in hon.items():
        if k.startswith("q2_token_"):
            lines.append(f"- {k}: hit {_pct(v['hit_rate']['hit_rate'], 1)}, slope {v['slope']['slope']:.2f}")
    for ven, v in hon.get("q2_by_venue", {}).items():
        lines.append(f"- venue {ven}: hit {_pct(v['hit_rate']['hit_rate'], 1)}, slope {v['slope']['slope']:.2f}")

    # Exploratory summary
    mag = expl.get("magnitude_buckets")
    if isinstance(mag, pd.DataFrame) and len(mag):
        lines += ["", "## EXPLORATORY — magnitude buckets", "", mag.to_markdown(index=False), ""]
    ud = expl.get("up_down", {})
    if ud:
        lines += [
            "## EXPLORATORY — up vs down",
            "",
            f"- Down moves: hit {_pct(ud.get('down', {}).get('hit_rate', {}).get('hit_rate', float('nan')), 1)} "
            f"(Wilson CI {_pct(ud.get('down', {}).get('hit_rate', {}).get('lo', float('nan')), 1)}–"
            f"{_pct(ud.get('down', {}).get('hit_rate', {}).get('hi', float('nan')), 1)}; n={ud.get('n_down')})",
            f"- Up moves: hit {_pct(ud.get('up', {}).get('hit_rate', {}).get('hit_rate', float('nan')), 1)} "
            f"(Wilson CI {_pct(ud.get('up', {}).get('hit_rate', {}).get('lo', float('nan')), 1)}–"
            f"{_pct(ud.get('up', {}).get('hit_rate', {}).get('hi', float('nan')), 1)}; n={ud.get('n_up')})",
            f"- Hit(up) − hit(down) = {_pct(ud.get('hit_up_minus_down', float('nan')), 1)} "
            f"(bootstrap 95% CI {_pct(ud.get('hit_up_minus_down_lo', float('nan')), 1)}–"
            f"{_pct(ud.get('hit_up_minus_down_hi', float('nan')), 1)}).",
            "",
        ]
    hol_verify = results.get("holiday_verification") or expl.get("holiday_verification")
    if hol_verify:
        lines += ["## Holiday-weekend list (CME / LBMA check)", "", hol_verify, ""]
    lines += [
        "## Manipulation test",
        "",
        "See [`manipulation_test.md`](manipulation_test.md) (exploratory). "
        "When n confirmed labels = 0, Links 1–4 are **pending labels** (not “not supported”).",
        "",
        "## Limitations",
        "",
        "- Small sample; regime change; provisional news labels; correlation ≠ causation.",
        "- Bybit geo-blocked; Kraken history short; on-chain Link 4 needs an indexed archive.",
        "",
    ]
    text = "\n".join(lines)
    path = cfg["paths"]["reports"] / "findings.md"
    path.write_text(text, encoding="utf-8")
    return text


def write_reports(cfg: dict[str, Any], results: dict[str, Any]) -> str:
    """Write findings + figures. Does not touch reports/x_article.md (hand-edited publish copy).
    x_thread.md is intentionally not regenerated — deleted in favor of x_article.md.
    """
    logger = setup_logging()
    fig_dir = cfg["paths"]["figures"]
    fig_dir.mkdir(parents=True, exist_ok=True)
    venues = results.get("venues_contributing") or _venues_in_sample(results, cfg)

    fig_q1_hist(results["q1"], cfg, fig_dir / "q1_drift_hist.png", venues)
    fig_q2_scatter(results["weekend_panel"], results["q2"], cfg, fig_dir / "q2_scatter.png", venues)
    fig_q3_stacked(results["q3"], cfg, fig_dir / "q3_who_closes.png", venues)
    if results.get("event_study") is not None:
        fig_q3_event_study(results["event_study"], cfg, fig_dir / "q3_event_study.png", venues)

    expl = results.get("exploratory") or {}
    mag = expl.get("magnitude_buckets")
    if isinstance(mag, pd.DataFrame):
        fig_q2_by_magnitude(mag, cfg, fig_dir / "q2_hit_by_magnitude.png", venues)
        mag.to_csv(cfg["paths"]["reports"] / "q2_magnitude_buckets.csv", index=False)
    if expl.get("manipulation"):
        write_manipulation_md(cfg, expl["manipulation"])

    results["q4"].to_csv(cfg["paths"]["reports"] / "q4_subgroups.csv", index=False)
    results["q5"].to_csv(cfg["paths"]["reports"] / "q5_top_dislocations.csv", index=False)

    md = write_findings(cfg, results)
    # Drop legacy auto-thread if present; published copy is x_article.md
    legacy = cfg["paths"]["reports"] / "x_thread.md"
    if legacy.exists():
        legacy.unlink()
        logger.info("Removed legacy %s (use x_article.md)", legacy.name)
    logger.info("Wrote findings.md, manipulation_test.md, figures/")
    return md
