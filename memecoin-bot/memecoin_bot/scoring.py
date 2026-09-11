"""Rank callers by consistency, not by reach.

The ranking deliberately ignores follower count, call volume and single
moonshots. A caller who lands 20 steady 3x runners outranks one whose
average is carried by a lone 400x with 30 zeros behind it.
"""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Iterable, Sequence

from .models import CallerStats, Outcome

# A call that never doubled is not a call worth following.
HIT_THRESHOLD = 2.0
MOON_THRESHOLD = 5.0
# Below this multiple at peak, the call was effectively dead on arrival.
RUG_THRESHOLD = 0.5
# Shrinkage constant: how many calls a caller needs before their score is
# taken at face value. With 5 calls a caller keeps ~50% of their raw score.
PRIOR_CALLS = 5
# Floor applied before taking logs so a zero does not blow up the geometry.
MULTIPLE_FLOOR = 0.05


def _percentile(values: Sequence[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = pct * (len(ordered) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[int(pos)]
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _geometric_mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    logs = [math.log(max(v, MULTIPLE_FLOOR)) for v in values]
    return math.exp(sum(logs) / len(logs))


def _consistency_score(
    *,
    calls: int,
    geometric_mean: float,
    worst_quartile: float,
    hit_rate: float,
    rug_rate: float,
    median_drawdown: float,
) -> float:
    """Blend the consistency signals into a single 0-100 number.

    Every term is a *typical case* measure. Nothing here rewards the tail,
    which is what keeps one lucky 400x from buying a top ranking.
    """
    # log2 keeps a 2x worth one point, a 4x two points - so a 100x cannot
    # dominate the way it would on a raw-multiple average.
    geo_term = max(0.0, math.log2(max(geometric_mean, MULTIPLE_FLOOR)))
    floor_term = max(0.0, math.log2(max(worst_quartile, MULTIPLE_FLOOR)))

    raw = (
        30.0 * min(geo_term / 3.0, 1.0)      # typical call size
        + 30.0 * hit_rate                     # how often it actually works
        + 25.0 * min(floor_term / 2.0, 1.0)   # how bad the bad days are
        + 15.0 * (1.0 - median_drawdown)      # was the peak exitable
    )
    raw *= 1.0 - 0.6 * rug_rate               # outright rugs hurt, hard

    # Small samples regress toward zero: 3 good calls is noise, not a record.
    shrinkage = calls / (calls + PRIOR_CALLS)
    return round(max(0.0, raw) * shrinkage, 2)


def score_caller(caller: str, outcomes: Sequence[Outcome]) -> CallerStats:
    peaks = [o.peak_multiple for o in outcomes]
    drawdowns = [o.drawdown_from_peak for o in outcomes]
    calls = len(outcomes)

    geo = _geometric_mean(peaks)
    worst_quartile = _percentile(peaks, 0.25)
    hit_rate = sum(p >= HIT_THRESHOLD for p in peaks) / calls
    moon_rate = sum(p >= MOON_THRESHOLD for p in peaks) / calls
    rug_rate = sum(p < RUG_THRESHOLD for p in peaks) / calls
    med_dd = median(drawdowns)

    best = max(outcomes, key=lambda o: o.peak_multiple)
    return CallerStats(
        caller=caller,
        calls=calls,
        median_peak_multiple=round(median(peaks), 2),
        mean_peak_multiple=round(sum(peaks) / calls, 2),
        geometric_mean=round(geo, 2),
        hit_rate_2x=round(hit_rate, 3),
        hit_rate_5x=round(moon_rate, 3),
        rug_rate=round(rug_rate, 3),
        median_drawdown=round(med_dd, 3),
        worst_quartile_multiple=round(worst_quartile, 2),
        consistency_score=_consistency_score(
            calls=calls,
            geometric_mean=geo,
            worst_quartile=worst_quartile,
            hit_rate=hit_rate,
            rug_rate=rug_rate,
            median_drawdown=med_dd,
        ),
        best_call=f"{best.callout.symbol or best.callout.mint[:6]} {best.peak_multiple:.1f}x",
        samples=list(outcomes),
    )


def rank_callers(outcomes: Iterable[Outcome], min_calls: int = 5) -> list[CallerStats]:
    """Score every caller with enough history and sort best-first."""
    by_caller: dict[str, list[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        by_caller[outcome.callout.caller].append(outcome)

    scored = [
        score_caller(caller, calls)
        for caller, calls in by_caller.items()
        if len(calls) >= min_calls
    ]
    scored.sort(key=lambda s: s.consistency_score, reverse=True)
    return scored
