"""Download and cache raw 1-minute series. Never invent or silently fill gaps.

Endpoint docs (cited for verification):
- Binance klines: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
  (also https://data-api.binance.vision mirror)
- OKX history-candles: https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-candlesticks-history
- Bybit v5 market kline: https://bybit-exchange.github.io/docs/v5/market/kline
- Kraken OHLC: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
  (REST keeps ~720 bars; prefer OHLCVT zip if available)
- Dukascopy historical: https://www.dukascopy.com/swiss/english/marketwatch/historical/
  datafeed pattern: https://datafeed.dukascopy.com/datafeed/XAUUSD/YYYY/MM/DD/BID_candles_min_1.bi5
- yfinance GC=F: Yahoo Finance futures
- GDELT DOC 2.0: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

from __future__ import annotations

import io
import lzma
import struct
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from src.logging_utils import setup_logging

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "gold-weekend-study/1.0 (research)"})


def _cache_path(raw: Path, name: str) -> Path:
    return raw / name


def _load_parquet(path: Path) -> pd.DataFrame | None:
    if path.exists():
        df = pd.read_parquet(path)
        if "ts" in df.columns:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
            df = df.set_index("ts").sort_index()
        elif not isinstance(df.index, pd.DatetimeIndex):
            return df
        else:
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")
        return df
    return None


def _save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if isinstance(out.index, pd.DatetimeIndex):
        out = out.reset_index()
        if out.columns[0] != "ts":
            out = out.rename(columns={out.columns[0]: "ts"})
    out.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# Dukascopy XAUUSD 1-min
# ---------------------------------------------------------------------------

def _dukascopy_day_url(base: str, instrument: str, day: date) -> str:
    # Dukascopy months are 0-indexed in the path
    return f"{base}/{instrument}/{day.year}/{day.month - 1:02d}/{day.day:02d}/BID_candles_min_1.bi5"


def _parse_bi5_minute_candles(payload: bytes, day: date) -> pd.DataFrame:
    """Parse Dukascopy LZMA-compressed 1-min candle file (24-byte big-endian records)."""
    if not payload:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    try:
        raw = lzma.decompress(payload)
    except lzma.LZMAError:
        raw = payload  # already decompressed in rare cases
    n = len(raw) // 24
    if n == 0:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    records = []
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    for i in range(n):
        chunk = raw[i * 24 : (i + 1) * 24]
        sec, o, c, low, high, vol = struct.unpack(">Ifffff", chunk)
        # struct: I + 5f = 4 + 20 = 24
        ts = base + timedelta(seconds=int(sec))
        records.append((ts, float(o), float(high), float(low), float(c), float(vol)))
    df = pd.DataFrame(records, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.set_index("ts").sort_index()
    return df


def fetch_dukascopy_xauusd(cfg: dict[str, Any], start: date, end: date, refresh: bool = False) -> pd.DataFrame:
    """Download Dukascopy XAUUSD 1-min bid candles.

    Primary: dukascopy-node CLI (retries + cache; docs https://www.dukascopy-node.app/).
    Fallback: direct .bi5 datafeed with backoff.
    """
    logger = setup_logging()
    raw = cfg["paths"]["raw"]
    path = _cache_path(raw, "dukascopy_xauusd_1m.parquet")
    if not refresh:
        cached = _load_parquet(path)
        if cached is not None and not cached.empty:
            logger.info("Dukascopy cache hit: %d bars", len(cached))
            return cached

    out = _fetch_dukascopy_via_node(raw, start, end, logger)
    if out is None or out.empty:
        logger.warning("dukascopy-node failed or empty — falling back to .bi5 datafeed")
        out = _fetch_dukascopy_via_bi5(cfg, start, end, logger)

    if out is None or out.empty:
        raise RuntimeError(
            f"Dukascopy returned no XAUUSD bars ({start}→{end}). "
            "Study cannot proceed without gold. Install Node.js and retry, "
            "or check https://datafeed.dukascopy.com availability."
        )
    out = out[~out.index.duplicated(keep="last")].sort_index()
    _save_parquet(out, path)
    logger.info("Dukascopy XAUUSD: %d bars (%s → %s)", len(out), start, end)
    return out


def _fetch_dukascopy_via_node(raw: Path, start: date, end: date, logger) -> pd.DataFrame | None:
    """Chunked downloads via npx dukascopy-node."""
    import shutil
    import subprocess

    if not shutil.which("npx"):
        logger.warning("npx not found — skip dukascopy-node path")
        return None

    dl_dir = raw / "dukascopy_node"
    dl_dir.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    # Monthly chunks keep CLI memory/timeouts manageable
    cursor = date(start.year, start.month, 1)
    end_exclusive = end + timedelta(days=1)
    while cursor < end_exclusive:
        if cursor.month == 12:
            nxt = date(cursor.year + 1, 1, 1)
        else:
            nxt = date(cursor.year, cursor.month + 1, 1)
        chunk_from = max(cursor, start)
        chunk_to = min(nxt, end_exclusive)
        chunk_dir = dl_dir / f"{chunk_from.isoformat()}_{chunk_to.isoformat()}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        existing = list(chunk_dir.glob("*.csv"))
        if not existing:
            cmd = [
                "npx", "--yes", "dukascopy-node",
                "-i", "xauusd",
                "-from", chunk_from.isoformat(),
                "-to", chunk_to.isoformat(),
                "-t", "m1",
                "-f", "csv",
                "-v",
                "--cache",
                "--retries", "5",
                "--batch-pause", "1000",
                "-dir", str(chunk_dir),
            ]
            logger.info("dukascopy-node %s → %s", chunk_from, chunk_to)
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                logger.warning("dukascopy-node chunk failed: %s", e)
                cursor = nxt
                continue
            existing = list(chunk_dir.glob("*.csv"))
        for csv_path in existing:
            try:
                df = pd.read_csv(csv_path)
            except Exception:  # noqa: BLE001
                continue
            # dukascopy-node columns: timestamp, open, high, low, close, volume (ms)
            ts_col = "timestamp" if "timestamp" in df.columns else df.columns[0]
            df["ts"] = pd.to_datetime(df[ts_col], utc=True, unit="ms", errors="coerce")
            if df["ts"].isna().all():
                df["ts"] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
            colmap = {c.lower(): c for c in df.columns}
            need = {}
            for k in ("open", "high", "low", "close", "volume"):
                if k in colmap:
                    need[k] = colmap[k]
                elif k.capitalize() in df.columns:
                    need[k] = k.capitalize()
            if "close" not in need:
                continue
            part = df.rename(columns={need[k]: k for k in need}).set_index("ts")
            part = part[[c for c in ("open", "high", "low", "close", "volume") if c in part.columns]]
            frames.append(part)
        cursor = nxt

    if not frames:
        return None
    out = pd.concat(frames).sort_index()
    out = out[(out.index.date >= start) & (out.index.date <= end)]
    return out


def _fetch_dukascopy_via_bi5(cfg: dict[str, Any], start: date, end: date, logger) -> pd.DataFrame:
    """Direct .bi5 download with retries/backoff (rate-limit sensitive)."""
    base = cfg["dukascopy"]["datafeed"]
    instrument = cfg["dukascopy"]["instrument"]
    frames: list[pd.DataFrame] = []
    day = start
    failures = 0
    while day <= end:
        if day.weekday() != 5:
            url = _dukascopy_day_url(base, instrument, day)
            ok = False
            for attempt in range(4):
                try:
                    r = SESSION.get(url, timeout=60)
                    if r.status_code == 200 and r.content:
                        df = _parse_bi5_minute_candles(r.content, day)
                        if not df.empty:
                            frames.append(df)
                        ok = True
                        break
                    if r.status_code == 404:
                        ok = True
                        break
                    time.sleep(1.5 * (attempt + 1))
                except requests.RequestException:
                    time.sleep(2.0 * (attempt + 1))
            if not ok:
                failures += 1
                logger.warning("Dukascopy bi5 failed for %s", day)
            time.sleep(0.35)
        day += timedelta(days=1)
    logger.info("bi5 fallback failures=%d frames=%d", failures, len(frames))
    if not frames:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return pd.concat(frames).sort_index()


# ---------------------------------------------------------------------------
# Binance / OKX / Bybit / Kraken klines
# ---------------------------------------------------------------------------

def _ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_binance_klines(
    cfg: dict[str, Any], symbol: str, start: datetime, end: datetime, refresh: bool = False
) -> pd.DataFrame:
    """Binance spot 1m klines from data-api.binance.vision only (v2.1).

    Docs: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
    Mirror: https://data-api.binance.vision
    Never mix with api.binance.us (that would be venue `binance_us`).
    """
    logger = setup_logging()
    path = _cache_path(cfg["paths"]["raw"], f"binance_{symbol}_1m.parquet")
    host_log = cfg["paths"]["raw"] / "binance_host_log.txt"
    if not refresh:
        cached = _load_parquet(path)
        if cached is not None and not cached.empty:
            return cached

    bases = list(cfg["binance"]["bases"])
    # Hard-reject .us mixing even if someone re-adds it to config
    bases = [b for b in bases if "binance.us" not in b.lower()]
    if not bases:
        logger.error("No allowed Binance hosts configured — dropping %s", symbol)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    primary = bases[0]
    limit = int(cfg["binance"]["limit"])
    rows: list[list] = []
    cursor = start
    hosts_seen: set[str] = set()
    failures = 0
    while cursor < end:
        url = f"{primary}{cfg['binance']['klines_path']}"
        params = {
            "symbol": symbol,
            "interval": "1m",
            "startTime": _ms(cursor),
            "endTime": _ms(end),
            "limit": limit,
        }
        try:
            r = SESSION.get(url, params=params, timeout=30)
            # Log the host that actually answered (after redirects)
            host = r.url.split("/")[2] if r.url else primary
            hosts_seen.add(host)
            with open(host_log, "a", encoding="utf-8") as hf:
                hf.write(f"{datetime.now(tz=timezone.utc).isoformat()} {symbol} host={host} status={r.status_code}\n")
            if host != primary.replace("https://", "").replace("http://", "").split("/")[0]:
                logger.warning("Binance responding host %s ≠ configured %s", host, primary)
            if r.status_code in (418, 429, 451) or r.status_code >= 500:
                failures += 1
                logger.warning("Binance %s host=%s HTTP %s", symbol, host, r.status_code)
                time.sleep(1.0)
                if failures > 20:
                    break
                continue
            r.raise_for_status()
            batch = r.json()
            failures = 0
        except requests.RequestException as e:
            failures += 1
            logger.warning("Binance %s via %s failed: %s", symbol, primary, e)
            if cfg["binance"].get("drop_on_host_failure", True) and failures > 10:
                logger.error(
                    "Binance vision failed for %s — dropping series (no fallback to .us/.com mix)",
                    symbol,
                )
                break
            time.sleep(0.5)
            continue
        if not batch:
            break
        rows.extend(batch)
        last_open = int(batch[-1][0])
        nxt = datetime.fromtimestamp(last_open / 1000, tz=timezone.utc) + timedelta(minutes=1)
        if nxt <= cursor:
            break
        cursor = nxt
        time.sleep(0.1)

    if not rows:
        logger.warning(
            "Binance %s: no bars from %s (hosts_seen=%s) — series dropped",
            symbol,
            primary,
            sorted(hosts_seen),
        )
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "tb_base", "tb_quote", "ignore",
        ],
    )
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df = df.set_index("ts")[["open", "high", "low", "close", "volume"]].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    _save_parquet(df, path)
    logger.info("Binance %s: %d bars from hosts=%s", symbol, len(df), sorted(hosts_seen))
    return df


def fetch_okx_klines(
    cfg: dict[str, Any], inst_id: str, start: datetime, end: datetime, refresh: bool = False
) -> pd.DataFrame:
    """OKX history-candles 1m. Newest-first pagination via `after` = older ts."""
    logger = setup_logging()
    safe = inst_id.replace("-", "")
    path = _cache_path(cfg["paths"]["raw"], f"okx_{safe}_1m.parquet")
    if not refresh:
        cached = _load_parquet(path)
        if cached is not None and not cached.empty:
            return cached

    url = f"{cfg['okx']['base']}{cfg['okx']['history_candles']}"
    limit = int(cfg["okx"]["limit"])
    rows: list = []
    # OKX: after = ts — request candles older than this
    after = str(_ms(end))
    start_ms = _ms(start)
    guard = 0
    while guard < 20000:
        guard += 1
        params = {"instId": inst_id, "bar": "1m", "limit": str(limit), "after": after}
        try:
            r = SESSION.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json().get("data") or []
        except requests.RequestException as e:
            logger.warning("OKX %s error: %s", inst_id, e)
            break
        if not data:
            break
        rows.extend(data)
        oldest = int(data[-1][0])
        if oldest <= start_ms:
            break
        after = str(oldest)
        time.sleep(0.05)

    if not rows:
        logger.warning("OKX %s: no bars", inst_id)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"])
    df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="ms", utc=True)
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    df["volume"] = df["vol"].astype(float)
    df = df.set_index("ts")[["open", "high", "low", "close", "volume"]].sort_index()
    df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
    df = df[~df.index.duplicated(keep="last")]
    _save_parquet(df, path)
    logger.info("OKX %s: %d bars", inst_id, len(df))
    return df


def fetch_bybit_klines(
    cfg: dict[str, Any], symbol: str, start: datetime, end: datetime, refresh: bool = False
) -> pd.DataFrame:
    """Bybit spot v5 kline 1m. Docs: /v5/market/kline.

    Some regions get HTTP 403 from api.bybit.com — we try api.bytick.com fallback
    and document empty coverage if both fail (do not invent bars).
    """
    logger = setup_logging()
    path = _cache_path(cfg["paths"]["raw"], f"bybit_{symbol}_1m.parquet")
    if not refresh:
        cached = _load_parquet(path)
        if cached is not None and not cached.empty:
            return cached

    bases = [cfg["bybit"]["base"], "https://api.bytick.com"]
    limit = int(cfg["bybit"]["limit"])
    rows: list = []
    cursor_end = _ms(end)
    start_ms = _ms(start)
    guard = 0
    base_i = 0
    while guard < 20000 and cursor_end > start_ms:
        guard += 1
        url = f"{bases[base_i % len(bases)]}{cfg['bybit']['kline_path']}"
        params = {
            "category": "spot",
            "symbol": symbol,
            "interval": "1",
            "start": start_ms,
            "end": cursor_end,
            "limit": limit,
        }
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 403:
                logger.warning("Bybit %s geo/forbidden via %s — trying fallback host", symbol, url)
                base_i += 1
                if base_i >= len(bases) * 2:
                    break
                continue
            r.raise_for_status()
            data = (r.json().get("result") or {}).get("list") or []
        except requests.RequestException as e:
            logger.warning("Bybit %s error: %s", symbol, e)
            base_i += 1
            if base_i >= len(bases) * 2:
                break
            continue
        if not data:
            break
        rows.extend(data)
        # Bybit returns newest first
        oldest = int(data[-1][0])
        if oldest <= start_ms:
            break
        cursor_end = oldest - 1
        time.sleep(0.05)

    if not rows:
        logger.warning("Bybit %s: no bars", symbol)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "turnover"])
    df["ts"] = pd.to_datetime(df["ts"].astype(np.int64), unit="ms", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df = df.set_index("ts")[["open", "high", "low", "close", "volume"]].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    _save_parquet(df, path)
    logger.info("Bybit %s: %d bars", symbol, len(df))
    return df


def fetch_kraken_ohlc(
    cfg: dict[str, Any], pair: str, start: datetime, end: datetime, refresh: bool = False, cache_name: str | None = None
) -> pd.DataFrame:
    """Kraken public OHLC (1-minute). Note: API returns a rolling ~720-bar window.

    Docs: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
    For full history we also try S3 OHLCVT dumps; on failure we keep whatever REST returns
    and document the limitation in the coverage table / research log.
    """
    logger = setup_logging()
    name = cache_name or f"kraken_{pair}_1m.parquet"
    path = _cache_path(cfg["paths"]["raw"], name)
    if not refresh:
        cached = _load_parquet(path)
        if cached is not None and not cached.empty:
            return cached

    # Try historical dump first (community / Kraken history bucket pattern)
    dump = _try_kraken_ohlcvt(pair, logger)
    if dump is not None and not dump.empty:
        dump = dump[(dump.index >= pd.Timestamp(start, tz="UTC")) & (dump.index <= pd.Timestamp(end, tz="UTC"))]
        if not dump.empty:
            _save_parquet(dump, path)
            logger.info("Kraken %s via OHLCVT dump: %d bars", pair, len(dump))
            return dump

    url = cfg["kraken"]["rest_ohlc"]
    # Walk forward with since= — still capped by Kraken's window, but we record what we get
    since = int(start.timestamp())
    end_ts = int(end.timestamp())
    rows: list = []
    guard = 0
    while guard < 500 and since < end_ts:
        guard += 1
        params = {"pair": pair, "interval": 1, "since": since}
        try:
            r = SESSION.get(url, params=params, timeout=30)
            r.raise_for_status()
            payload = r.json()
        except requests.RequestException as e:
            logger.warning("Kraken OHLC %s error: %s", pair, e)
            break
        if payload.get("error"):
            logger.warning("Kraken OHLC %s API error: %s", pair, payload["error"])
            break
        result = payload.get("result") or {}
        key = next((k for k in result if k != "last"), None)
        if not key:
            break
        batch = result[key]
        if not batch:
            break
        rows.extend(batch)
        last = int(result.get("last") or batch[-1][0])
        if last <= since:
            break
        since = last
        time.sleep(0.3)

    if not rows:
        logger.warning(
            "Kraken %s: no historical depth via REST (expected ~720-bar cap). "
            "Documented — use as USD-quoted robustness when available.",
            pair,
        )
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "vwap", "volume", "count"])
    df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="s", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df = df.set_index("ts")[["open", "high", "low", "close", "volume"]].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    _save_parquet(df, path)
    logger.info("Kraken %s via REST: %d bars (may be truncated)", pair, len(df))
    return df


def _try_kraken_ohlcvt(pair: str, logger) -> pd.DataFrame | None:
    """Attempt known public OHLCVT CSV locations; return None if unavailable."""
    candidates = [
        f"https://s3-eu-west-1.amazonaws.com/history.kraken.com/{pair}_1.csv.gz",
        f"https://history.kraken.com/{pair}_1.csv.gz",
    ]
    for url in candidates:
        try:
            r = SESSION.get(url, timeout=60)
            if r.status_code != 200:
                continue
            df = pd.read_csv(
                io.BytesIO(r.content),
                compression="gzip",
                header=None,
                names=["ts", "open", "high", "low", "close", "volume", "trades"],
            )
            df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True)
            df = df.set_index("ts")[["open", "high", "low", "close", "volume"]].sort_index()
            logger.info("Downloaded Kraken OHLCVT from %s", url)
            return df
        except Exception as e:  # noqa: BLE001 — best-effort fallback
            logger.info("Kraken OHLCVT miss %s: %s", url, e)
    return None


def fetch_yfinance_gcf(cfg: dict[str, Any], start: date, end: date, refresh: bool = False) -> pd.DataFrame:
    """Hourly GC=F via yfinance as reopen-gap cross-check."""
    logger = setup_logging()
    path = _cache_path(cfg["paths"]["raw"], "yfinance_gcf_1h.parquet")
    if not refresh:
        cached = _load_parquet(path)
        if cached is not None and not cached.empty:
            return cached
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed — GC=F cross-check skipped")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    ticker = yf.Ticker(cfg["yfinance"]["symbol"])
    df = ticker.history(start=str(start), end=str(end + timedelta(days=1)), interval="1h", auto_adjust=False)
    if df.empty:
        logger.warning("yfinance GC=F returned empty")
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df.index = pd.to_datetime(df.index, utc=True)
    out = df[["open", "high", "low", "close", "volume"]].sort_index()
    _save_parquet(out, path)
    logger.info("yfinance GC=F: %d hourly bars", len(out))
    return out


def fetch_bitstamp_ohlc(
    pair: str, start: datetime, end: datetime, refresh: bool = False, raw: Path | None = None
) -> pd.DataFrame:
    """Bitstamp 1-min OHLC. Docs: https://www.bitstamp.net/api/#tag/Market-info/operation/GetOHLCData

    pair examples: usdtusd, usdcusd. Paginate with start/end unix seconds, limit≤1000.
    """
    logger = setup_logging()
    cache = _cache_path(raw or Path("data/raw"), f"bitstamp_{pair}_1m.parquet")
    if not refresh:
        cached = _load_parquet(cache)
        if cached is not None and not cached.empty:
            logger.info("Bitstamp %s cache hit: %d bars", pair, len(cached))
            return cached

    url = f"https://www.bitstamp.net/api/v2/ohlc/{pair}/"
    rows: list = []
    cursor = int(start.timestamp())
    end_ts = int(end.timestamp())
    guard = 0
    while cursor < end_ts and guard < 5000:
        guard += 1
        params = {"step": 60, "limit": 1000, "start": cursor, "end": min(cursor + 1000 * 60, end_ts)}
        try:
            r = SESSION.get(url, params=params, timeout=30)
            r.raise_for_status()
            batch = ((r.json() or {}).get("data") or {}).get("ohlc") or []
        except requests.RequestException as e:
            logger.warning("Bitstamp %s error: %s", pair, e)
            break
        if not batch:
            break
        rows.extend(batch)
        last = int(batch[-1]["timestamp"])
        nxt = last + 60
        if nxt <= cursor:
            break
        cursor = nxt
        time.sleep(0.15)

    if not rows:
        logger.warning("Bitstamp %s: no bars", pair)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["timestamp"].astype(np.int64), unit="s", utc=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)
    df = df.set_index("ts")[["open", "high", "low", "close", "volume"]].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    _save_parquet(df, cache)
    logger.info("Bitstamp %s: %d bars", pair, len(df))
    return df


def fetch_stablecoin_usd(cfg: dict[str, Any], start: datetime, end: datetime, refresh: bool = False) -> dict[str, pd.DataFrame]:
    """USDT/USD and USDC/USD — Bitstamp primary (full history), Kraken as backup.

    Kraken REST OHLC only keeps ~720 bars; Bitstamp paginated OHLC covers the sample.
    """
    logger = setup_logging()
    raw = cfg["paths"]["raw"]
    usdt = fetch_bitstamp_ohlc("usdtusd", start, end, refresh=refresh, raw=raw)
    usdc = fetch_bitstamp_ohlc("usdcusd", start, end, refresh=refresh, raw=raw)
    if usdt.empty:
        logger.warning("Bitstamp USDT empty — falling back to Kraken (short history)")
        usdt = fetch_kraken_ohlc(
            cfg, cfg["kraken"]["pair_usdt"], start, end, refresh=refresh, cache_name="kraken_USDTZUSD_1m.parquet"
        )
    if usdc.empty:
        logger.warning("Bitstamp USDC empty — falling back to Kraken")
        usdc = fetch_kraken_ohlc(
            cfg, cfg["kraken"]["pair_usdc"], start, end, refresh=refresh, cache_name="kraken_USDCUSD_1m.parquet"
        )
    return {"USDT": usdt, "USDC": usdc}


def run_fetch(cfg: dict[str, Any], refresh: bool = False) -> dict[str, Any]:
    """Fetch all raw series; return dict of frames + info summary."""
    logger = setup_logging()
    from src.calendar import latest_complete_friday

    start_d = date.fromisoformat(str(cfg["sample_start"]))
    # Need a few weekdays before first Friday for B_weekday
    fetch_start = start_d - timedelta(days=10)
    # Always fetch through latest complete weekend so post-freeze OOS rows can be built.
    end_d = latest_complete_friday()
    # Pull through Monday after last Friday + buffer
    fetch_end_d = end_d + timedelta(days=4)
    start_dt = datetime(fetch_start.year, fetch_start.month, fetch_start.day, tzinfo=timezone.utc)
    end_dt = datetime(fetch_end_d.year, fetch_end_d.month, fetch_end_d.day, 23, 59, tzinfo=timezone.utc)

    info: dict[str, Any] = {"start": str(fetch_start), "end": str(fetch_end_d), "series": {}}

    gold = fetch_dukascopy_xauusd(cfg, fetch_start, fetch_end_d, refresh=refresh)
    info["series"]["dukascopy_xauusd"] = len(gold)

    gcf = fetch_yfinance_gcf(cfg, fetch_start, fetch_end_d, refresh=refresh)
    info["series"]["yfinance_gcf"] = len(gcf)

    stables = fetch_stablecoin_usd(cfg, start_dt, end_dt, refresh=refresh)
    info["series"]["usdt_usd"] = len(stables["USDT"])
    info["series"]["usdc_usd"] = len(stables["USDC"])

    btc = fetch_binance_klines(cfg, "BTCUSDT", start_dt, end_dt, refresh=refresh)
    info["series"]["btcusdt"] = len(btc)

    tokens: dict[str, pd.DataFrame] = {}
    for v in cfg["venues"]:
        key = f"{v['venue']}:{v['symbol']}"
        try:
            if v["venue"] == "binance":
                df = fetch_binance_klines(cfg, v["symbol"], start_dt, end_dt, refresh=refresh)
            elif v["venue"] == "okx":
                df = fetch_okx_klines(cfg, v["symbol"], start_dt, end_dt, refresh=refresh)
            elif v["venue"] == "bybit":
                df = fetch_bybit_klines(cfg, v["symbol"], start_dt, end_dt, refresh=refresh)
            elif v["venue"] == "kraken":
                df = fetch_kraken_ohlc(cfg, v["symbol"], start_dt, end_dt, refresh=refresh)
            else:
                logger.warning("Unknown venue %s", v["venue"])
                continue
            tokens[key] = df
            info["series"][key] = len(df)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed fetching %s: %s", key, e)
            tokens[key] = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
            info["series"][key] = 0

    return {
        "gold": gold,
        "gcf": gcf,
        "stables": stables,
        "btc": btc,
        "tokens": tokens,
        "info": info,
        "fetch_start": fetch_start,
        "fetch_end": fetch_end_d,
    }


def print_fetch_summary(info: dict[str, Any]) -> None:
    print("\n=== Fetch summary ===")
    print(f"Range: {info['start']} → {info['end']}")
    for k, n in info["series"].items():
        print(f"  {k}: {n:,} bars")
    print("=====================\n")
