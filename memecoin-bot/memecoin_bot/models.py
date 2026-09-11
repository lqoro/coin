"""Core data types for callout tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # pump.fun and most Solana indexers hand back millisecond epochs.
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


@dataclass(frozen=True)
class Callout:
    """A single "buy this" post from a caller, at a known point in time."""

    caller: str
    mint: str
    called_at: datetime
    entry_mcap_usd: float
    symbol: str = ""
    source: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> "Callout":
        return cls(
            caller=raw["caller"].strip().lower(),
            mint=raw["mint"],
            called_at=_parse_ts(raw["called_at"]),
            entry_mcap_usd=float(raw["entry_mcap_usd"]),
            symbol=raw.get("symbol", ""),
            source=raw.get("source", ""),
        )


@dataclass(frozen=True)
class Outcome:
    """What the token actually did after the call."""

    callout: Callout
    peak_mcap_usd: float
    mcap_now_usd: float
    minutes_to_peak: float | None = None

    @property
    def peak_multiple(self) -> float:
        """Best exit available to someone who bought the call."""
        if self.entry <= 0:
            return 0.0
        return self.peak_mcap_usd / self.entry

    @property
    def held_multiple(self) -> float:
        """What a buyer who never sold is holding."""
        if self.entry <= 0:
            return 0.0
        return self.mcap_now_usd / self.entry

    @property
    def entry(self) -> float:
        return self.callout.entry_mcap_usd

    @property
    def drawdown_from_peak(self) -> float:
        """Fraction given back from the peak. 1.0 means it round-tripped to zero."""
        if self.peak_mcap_usd <= 0:
            return 1.0
        return max(0.0, 1.0 - self.mcap_now_usd / self.peak_mcap_usd)

    @classmethod
    def from_dict(cls, raw: dict) -> "Outcome":
        return cls(
            callout=Callout.from_dict(raw),
            peak_mcap_usd=float(raw["peak_mcap_usd"]),
            mcap_now_usd=float(raw["mcap_now_usd"]),
            minutes_to_peak=raw.get("minutes_to_peak"),
        )


@dataclass
class CallerStats:
    """Consistency-first scorecard for one caller."""

    caller: str
    calls: int
    median_peak_multiple: float
    mean_peak_multiple: float
    geometric_mean: float
    hit_rate_2x: float
    hit_rate_5x: float
    rug_rate: float
    median_drawdown: float
    worst_quartile_multiple: float
    consistency_score: float
    best_call: str = ""
    samples: list[Outcome] = field(default_factory=list, repr=False)
