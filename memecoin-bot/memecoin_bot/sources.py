"""Callout ingestion and post-call price resolution.

Callouts come in as JSONL - one object per call - because the places
callers actually post (Telegram, X, Discord) each need their own scraper
and none of them expose a common API. Anything that can emit:

    {"caller": "...", "mint": "...", "called_at": "...", "entry_mcap_usd": 1234}

feeds this pipeline. Peak/current market caps are then resolved against
pump.fun, with Dexscreener as the fallback for anything that graduated
to Raydium and fell off the pump.fun index.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Iterator

from .models import Callout, Outcome

PUMP_COIN_URL = "https://frontend-api-v3.pump.fun/coins/{mint}"
PUMP_CANDLES_URL = "https://frontend-api-v3.pump.fun/candlesticks/{mint}?timeframe=5&limit=1000"
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{mint}"
USER_AGENT = "memecoin-bot/0.1"
REQUEST_TIMEOUT = 20.0
# pump.fun throttles aggressively; stay under it rather than getting banned.
RATE_LIMIT_SECONDS = float(os.environ.get("MEMECOIN_BOT_RATE_LIMIT", "0.35"))


class SourceError(RuntimeError):
    """Raised when upstream price data cannot be resolved for a mint."""


def load_callouts(path: str | Path) -> list[Callout]:
    """Read a JSONL callout log. Blank lines and `#` comments are skipped."""
    callouts = []
    with open(path, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                callouts.append(Callout.from_dict(json.loads(line)))
            except (ValueError, KeyError) as exc:
                raise SourceError(f"{path}:{lineno}: bad callout record ({exc})") from exc
    return callouts


def load_outcomes(path: str | Path) -> list[Outcome]:
    """Read a pre-resolved outcome log (callout fields plus peak/current mcap)."""
    outcomes = []
    with open(path, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                outcomes.append(Outcome.from_dict(json.loads(line)))
            except (ValueError, KeyError) as exc:
                raise SourceError(f"{path}:{lineno}: bad outcome record ({exc})") from exc
    return outcomes


def _get_json(url: str) -> dict | list:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SourceError(f"fetch failed for {url}: {exc}") from exc


def _pump_marketcaps(callout: Callout) -> tuple[float, float, float | None]:
    """Peak mcap after the call, current mcap, and minutes to peak."""
    coin = _get_json(PUMP_COIN_URL.format(mint=callout.mint))
    now = float(coin.get("usd_market_cap") or 0.0)

    candles = _get_json(PUMP_CANDLES_URL.format(mint=callout.mint))
    if not isinstance(candles, list) or not candles:
        raise SourceError(f"no candles for {callout.mint}")

    called_epoch = callout.called_at.timestamp()
    supply = float(coin.get("total_supply") or 0.0) / 1e6 or None

    peak, peak_ts = 0.0, None
    for candle in candles:
        ts = float(candle.get("timestamp") or 0)
        if ts < called_epoch:
            continue
        high = float(candle.get("high") or 0.0)
        mcap = high * supply if supply else high
        if mcap > peak:
            peak, peak_ts = mcap, ts

    if peak <= 0:
        raise SourceError(f"no post-call candles for {callout.mint}")
    minutes = (peak_ts - called_epoch) / 60 if peak_ts else None
    return peak, now, minutes


def _dexscreener_marketcap(mint: str) -> float:
    payload = _get_json(DEXSCREENER_URL.format(mint=mint))
    pairs = (payload or {}).get("pairs") or []
    if not pairs:
        raise SourceError(f"dexscreener has no pairs for {mint}")
    # Deepest pool is the honest price; shallow ones are trivially spoofed.
    best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0.0))
    return float(best.get("marketCap") or best.get("fdv") or 0.0)


def resolve_outcomes(callouts: Iterable[Callout], *, skip_errors: bool = True) -> Iterator[Outcome]:
    """Turn callouts into outcomes by pricing each mint after its call."""
    for callout in callouts:
        try:
            peak, now, minutes = _pump_marketcaps(callout)
        except SourceError:
            try:
                now = _dexscreener_marketcap(callout.mint)
                # Without candles the best defensible peak is the current cap.
                peak, minutes = max(now, callout.entry_mcap_usd), None
            except SourceError:
                if not skip_errors:
                    raise
                continue
        yield Outcome(callout=callout, peak_mcap_usd=peak, mcap_now_usd=now, minutes_to_peak=minutes)
        time.sleep(RATE_LIMIT_SECONDS)
