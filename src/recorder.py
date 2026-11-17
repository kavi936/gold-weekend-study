"""Forward L2 + liquidation recorder. NEVER imported by study analysis.

Stores hourly parquet under data/forward/. Historical depth is not freely
available — this archive exists so a later strategy phase can cost trades.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.calendar import ET, et_to_utc, parse_hhmm
from src.logging_utils import setup_logging

try:
    import websocket
except ImportError:  # pragma: no cover
    websocket = None

try:
    import certifi
    import ssl

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL_CONTEXT = None


def write_heartbeat(forward: Path, message: str) -> None:
    path = forward / "heartbeat.txt"
    path.write_text(f"{datetime.utcnow().isoformat()}Z {message}\n", encoding="utf-8")


def write_monday_summary(forward: Path) -> Path:
    """Summarize minutes/gaps recorded per stream for the latest weekend window."""
    gaps_path = forward / "gaps.log"
    gap_lines = gaps_path.read_text(encoding="utf-8").splitlines() if gaps_path.exists() else []
    rows = []
    for venue_dir in sorted(p for p in forward.iterdir() if p.is_dir()):
        for sym_dir in sorted(p for p in venue_dir.iterdir() if p.is_dir()):
            files = list(sym_dir.glob("*.parquet"))
            n_rows = 0
            for f in files:
                try:
                    n_rows += len(pd.read_parquet(f))
                except Exception:  # noqa: BLE001
                    pass
            rows.append({"venue": venue_dir.name, "symbol": sym_dir.name, "hourly_files": len(files), "snapshots": n_rows})
    summary = pd.DataFrame(rows)
    out = forward / "monday_summary.csv"
    summary.to_csv(out, index=False)
    (forward / "monday_summary.md").write_text(
        "# Recorder Monday summary\n\n"
        f"Gap log lines: {len(gap_lines)}\n\n"
        + (summary.to_markdown(index=False) if len(summary) else "_no streams_")
        + "\n\nNote: a sleeping laptop = gaps. Run on an always-on machine.\n",
        encoding="utf-8",
    )
    return out


def recorder_window(now_et: datetime | None = None) -> tuple[datetime, datetime]:
    """Current or next Fri 16:00 ET → Mon 02:00 ET window."""
    now = now_et or datetime.now(tz=ET)
    # Find Friday of this week (or previous if we're Mon before 02:00 still in window)
    d = now.date()
    # If Mon and before 02:00, window started previous Friday
    if d.weekday() == 0 and now.time() < parse_hhmm("02:00"):
        friday = d - timedelta(days=3)
    elif d.weekday() >= 4:  # Fri=4, Sat=5, Sun=6
        # Friday of current week
        friday = d - timedelta(days=(d.weekday() - 4))
    else:
        # Mon after 02:00 .. Thu → next Friday
        friday = d + timedelta(days=(4 - d.weekday()))

    start = datetime.combine(friday, parse_hhmm("16:00"), tzinfo=ET)
    end = datetime.combine(friday + timedelta(days=3), parse_hhmm("02:00"), tzinfo=ET)
    if now > end:
        # roll to next Friday
        friday = friday + timedelta(days=7)
        start = datetime.combine(friday, parse_hhmm("16:00"), tzinfo=ET)
        end = datetime.combine(friday + timedelta(days=3), parse_hhmm("02:00"), tzinfo=ET)
    return start, end


def _hourly_path(forward: Path, venue: str, symbol: str, ts: datetime) -> Path:
    utc = ts.astimezone(ET).astimezone(__import__("zoneinfo").ZoneInfo("UTC"))
    hour = utc.strftime("%Y-%m-%dT%H")
    p = forward / venue / symbol
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{hour}.parquet"


def _append_parquet(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    if path.exists():
        old = pd.read_parquet(path)
        df = pd.concat([old, df], ignore_index=True)
    df.to_parquet(path, index=False)


def _log_gap(forward: Path, message: str) -> None:
    path = forward / "gaps.log"
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()}Z {message}\n")


class BookBuffer:
    """Accumulate snapshots and flush hourly."""

    def __init__(self, forward: Path, venue: str, symbol: str):
        self.forward = forward
        self.venue = venue
        self.symbol = symbol
        self.rows: list[dict] = []
        self.lock = threading.Lock()
        self.last_snap: datetime | None = None

    def add(self, row: dict) -> None:
        with self.lock:
            self.rows.append(row)
            self.last_snap = datetime.utcnow()

    def flush(self) -> None:
        with self.lock:
            if not self.rows:
                return
            # Split by hour
            by_hour: dict[str, list] = {}
            for r in self.rows:
                ts = pd.Timestamp(r["ts"])
                key = ts.strftime("%Y-%m-%dT%H")
                by_hour.setdefault(key, []).append(r)
            self.rows = []
        for key, rows in by_hour.items():
            path = self.forward / self.venue / self.symbol / f"{key}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            _append_parquet(path, rows)


def _normalize_levels(levels, n: int) -> list[list[float]]:
    out = []
    for lv in levels[:n]:
        if isinstance(lv, dict):
            out.append([float(lv.get("price") or lv.get("px") or 0), float(lv.get("size") or lv.get("sz") or 0)])
        else:
            out.append([float(lv[0]), float(lv[1])])
    while len(out) < n:
        out.append([0.0, 0.0])
    return out


def resolve_symbols(cfg: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return list of (venue, symbol, kind) after light discovery. Skip + log if missing."""
    logger = setup_logging()
    out: list[tuple[str, str, str]] = []
    tokens = cfg["recorder"]["tokens"]
    # Static map for spot; Hyperliquid verified via meta when possible
    mapping = {
        ("binance", "PAXG"): ("PAXGUSDT", "spot"),
        ("binance", "XAUT"): ("XAUTUSDT", "spot"),
        ("okx", "PAXG"): ("PAXG-USDT", "spot"),
        ("okx", "XAUT"): ("XAUT-USDT", "spot"),
        ("bybit", "PAXG"): ("PAXGUSDT", "spot"),
        ("bybit", "XAUT"): ("XAUTUSDT", "spot"),
        ("hyperliquid", "PAXG"): ("PAXG", "perp"),
        ("hyperliquid", "XAUT"): ("XYZ100", "perp"),  # placeholder — verified via meta
    }
    # Hyperliquid meta: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
    hl_names = _hyperliquid_meta_names()
    logger.info("Hyperliquid meta names sample: %s", sorted(list(hl_names))[:30])
    for venue in cfg["recorder"]["venues"]:
        for tok in tokens:
            key = (venue, tok)
            if venue == "hyperliquid":
                # Prefer exact API names; known aliases only if present in meta (verified live).
                # Observed 2026-11-17: PAXG in spotMeta; XAUT appears as XAUT0 (not bare XAUT).
                aliases = {
                    "PAXG": ["PAXG"],
                    "XAUT": ["XAUT0", "XAUT"],
                }
                match = None
                for cand in aliases.get(tok, [tok]):
                    if cand in hl_names:
                        match = cand
                        break
                    for n in hl_names:
                        if n and cand.lower() == n.lower():
                            match = n
                            break
                    if match:
                        break
                if match:
                    out.append((venue, match, "perp"))
                    logger.info("Hyperliquid mapped %s → %s", tok, match)
                else:
                    logger.warning("Hyperliquid: no meta/spotMeta match for %s — skip", tok)
                    _log_gap(cfg["paths"]["forward"], f"skip hyperliquid {tok}: not in meta/spotMeta")
                continue
            if key in mapping:
                sym, kind = mapping[key]
                out.append((venue, sym, kind))
            else:
                logger.warning("No symbol map for %s %s", venue, tok)
    return out


def _hyperliquid_meta_names() -> set[str]:
    """Perp meta + spotMeta + HIP-3 dex meta. Docs: hyperliquid info endpoint."""
    import requests

    names: set[str] = set()
    try:
        r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "meta"}, timeout=20)
        r.raise_for_status()
        universe = (r.json() or {}).get("universe") or []
        names |= {u.get("name") for u in universe if u.get("name")}
    except Exception:  # noqa: BLE001
        pass
    try:
        r = requests.post("https://api.hyperliquid.xyz/info", json={"type": "spotMeta"}, timeout=20)
        r.raise_for_status()
        tokens = (r.json() or {}).get("tokens") or []
        names |= {t.get("name") for t in tokens if t.get("name")}
        universe = (r.json() or {}).get("universe") or []
        for u in universe:
            if u.get("name"):
                names.add(u["name"])
    except Exception:  # noqa: BLE001
        pass
    # HIP-3 builder DEXes sometimes expose gold under a dex-scoped meta
    for dex in ("xyz", "flx", ""):
        try:
            payload = {"type": "meta"}
            if dex:
                payload["dex"] = dex
            r = requests.post("https://api.hyperliquid.xyz/info", json=payload, timeout=20)
            if r.status_code != 200:
                continue
            universe = (r.json() or {}).get("universe") or []
            names |= {u.get("name") for u in universe if u.get("name")}
        except Exception:  # noqa: BLE001
            continue
    return {n for n in names if n}


def snapshot_rest_once(venue: str, symbol: str, levels: int) -> dict | None:
    """One-shot REST depth snapshot (works without long-lived WS)."""
    import requests

    try:
        if venue == "binance":
            # https://binance-docs.github.io/apidocs/spot/en/#order-book
            r = requests.get(
                "https://api.binance.com/api/v3/depth",
                params={"symbol": symbol, "limit": levels},
                timeout=15,
            )
            if r.status_code != 200:
                r = requests.get(
                    "https://data-api.binance.vision/api/v3/depth",
                    params={"symbol": symbol, "limit": levels},
                    timeout=15,
                )
            r.raise_for_status()
            data = r.json()
            return {
                "bids": _normalize_levels(data.get("bids", []), levels),
                "asks": _normalize_levels(data.get("asks", []), levels),
            }
        if venue == "okx":
            # https://www.okx.com/docs-v5/en/#order-book-trading-market-data-get-order-book
            r = requests.get(
                "https://www.okx.com/api/v5/market/books",
                params={"instId": symbol, "sz": str(levels)},
                timeout=15,
            )
            r.raise_for_status()
            arr = (r.json() or {}).get("data") or []
            if not arr:
                return None
            book = arr[0]
            return {
                "bids": _normalize_levels(book.get("bids", []), levels),
                "asks": _normalize_levels(book.get("asks", []), levels),
            }
        if venue == "bybit":
            # https://bybit-exchange.github.io/docs/v5/market/orderbook
            r = requests.get(
                "https://api.bybit.com/v5/market/orderbook",
                params={"category": "spot", "symbol": symbol, "limit": levels},
                timeout=15,
            )
            r.raise_for_status()
            result = (r.json() or {}).get("result") or {}
            return {
                "bids": _normalize_levels(result.get("b", []), levels),
                "asks": _normalize_levels(result.get("a", []), levels),
            }
        if venue == "hyperliquid":
            # https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals#retrieve-l2-snapshot
            r = requests.post(
                "https://api.hyperliquid.xyz/info",
                json={"type": "l2Book", "coin": symbol},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json() or {}
            levels_data = data.get("levels") or [[], []]
            bids = [[float(x["px"]), float(x["sz"])] for x in levels_data[0][:levels]]
            asks = [[float(x["px"]), float(x["sz"])] for x in levels_data[1][:levels]]
            return {"bids": _normalize_levels(bids, levels), "asks": _normalize_levels(asks, levels)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    return None


def record_loop(cfg: dict[str, Any], once: bool = False, max_seconds: float | None = None) -> None:
    """Poll L2 every snapshot_interval_sec during the recorder window."""
    logger = setup_logging()
    forward: Path = cfg["paths"]["forward"]
    forward.mkdir(parents=True, exist_ok=True)
    levels = int(cfg["recorder"]["depth_levels"])
    interval = int(cfg["recorder"]["snapshot_interval_sec"])
    start, end = recorder_window()
    logger.info("Recorder window %s → %s ET", start, end)

    symbols = resolve_symbols(cfg)
    buffers = {(v, s): BookBuffer(forward, v, s) for v, s, _ in symbols}
    liq_buffer = BookBuffer(forward, "binance", "forceOrder")

    # Binance forceOrder via websocket in background if available
    stop = threading.Event()

    def _force_order_thread():
        if websocket is None:
            logger.warning("websocket-client not installed — skipping forceOrder stream")
            return
        perps = cfg["recorder"].get("binance_perp_symbols") or []
        # Combined stream
        # Docs: https://binance-docs.github.io/apidocs/futures/en/#liquidation-order-streams
        streams = "/".join(f"{s.lower()}@forceOrder" for s in perps)
        if not streams:
            return
        url = f"wss://fstream.binance.com/stream?streams={streams}"

        def on_message(ws, message):
            try:
                payload = json.loads(message)
                data = payload.get("data") or payload
                o = data.get("o") or {}
                liq_buffer.add(
                    {
                        "ts": datetime.utcnow().isoformat() + "Z",
                        "symbol": o.get("s"),
                        "side": o.get("S"),
                        "price": float(o.get("p") or 0),
                        "qty": float(o.get("q") or 0),
                        "raw": json.dumps(o),
                    }
                )
            except Exception as e:  # noqa: BLE001
                _log_gap(forward, f"forceOrder parse error: {e}")

        def on_error(ws, err):
            _log_gap(forward, f"forceOrder ws error: {err}")

        while not stop.is_set():
            try:
                ws = websocket.WebSocketApp(url, on_message=on_message, on_error=on_error)
                # macOS: use certifi CA bundle if available (CERTIFICATE_VERIFY_FAILED)
                sslopt = {"context": _SSL_CONTEXT} if _SSL_CONTEXT is not None else None
                ws.run_forever(ping_interval=20, sslopt=sslopt)
            except Exception as e:  # noqa: BLE001
                _log_gap(forward, f"forceOrder reconnect: {e}")
                time.sleep(5)

    t = threading.Thread(target=_force_order_thread, daemon=True)
    t.start()

    t0 = time.time()
    gaps = 0
    try:
        while True:
            now = datetime.now(tz=ET)
            force = bool(cfg.get("_force_record"))
            if now < start and not force:
                if once:
                    logger.info("Outside window (starts %s). Use --force to snapshot now.", start)
                    break
                time.sleep(min(30, max(1, (start - now).total_seconds())))
                continue
            if now > end and not force:
                logger.info("Window ended.")
                break

            for venue, symbol, _kind in symbols:
                snap = snapshot_rest_once(venue, symbol, levels)
                ts = datetime.utcnow().isoformat() + "Z"
                if snap is None or snap.get("error"):
                    gaps += 1
                    _log_gap(forward, f"{venue} {symbol}: {snap}")
                    continue
                buffers[(venue, symbol)].add(
                    {
                        "ts": ts,
                        "venue": venue,
                        "symbol": symbol,
                        "bids": json.dumps(snap["bids"]),
                        "asks": json.dumps(snap["asks"]),
                    }
                )

            if int(time.time()) % 60 < interval:
                for buf in buffers.values():
                    buf.flush()
                liq_buffer.flush()
                write_heartbeat(forward, f"flushed gaps={gaps} symbols={len(symbols)}")
                logger.info("Heartbeat: buffers flushed, gaps=%d", gaps)

            if once:
                for buf in buffers.values():
                    buf.flush()
                liq_buffer.flush()
                logger.info("Single snapshot cycle done (gaps=%d)", gaps)
                break

            if max_seconds is not None and (time.time() - t0) >= max_seconds:
                break
            time.sleep(interval)
    finally:
        stop.set()
        for buf in buffers.values():
            buf.flush()
        liq_buffer.flush()
        logger.info("Recorder stopped. Total gap events=%d", gaps)
