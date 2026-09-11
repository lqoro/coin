"""Human-readable and machine-readable rendering of the leaderboard."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Sequence

from .models import CallerStats

COLUMNS = [
    ("caller", "CALLER", 22),
    ("consistency_score", "SCORE", 7),
    ("calls", "CALLS", 6),
    ("median_peak_multiple", "MED x", 7),
    ("geometric_mean", "GEO x", 7),
    ("worst_quartile_multiple", "P25 x", 7),
    ("hit_rate_2x", "2x%", 6),
    ("hit_rate_5x", "5x%", 6),
    ("rug_rate", "RUG%", 6),
    ("median_drawdown", "DD%", 6),
]
PERCENT_FIELDS = {"hit_rate_2x", "hit_rate_5x", "rug_rate", "median_drawdown"}


def _cell(stats: CallerStats, field: str) -> str:
    value = getattr(stats, field)
    if field in PERCENT_FIELDS:
        return f"{value * 100:.0f}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_table(ranked: Sequence[CallerStats]) -> str:
    if not ranked:
        return "No callers cleared the minimum-calls threshold."

    header = "  ".join(label.ljust(width) for _, label, width in COLUMNS)
    lines = [header, "-" * len(header)]
    for stats in ranked:
        lines.append("  ".join(_cell(stats, field).ljust(width) for field, _, width in COLUMNS))

    top = ranked[0]
    lines += [
        "",
        f"Most consistent: {top.caller} - score {top.consistency_score} over {top.calls} calls, "
        f"median {top.median_peak_multiple}x, {top.hit_rate_2x * 100:.0f}% of calls doubled, "
        f"{top.rug_rate * 100:.0f}% rugged. Best: {top.best_call}.",
    ]
    return "\n".join(lines)


def render_json(ranked: Sequence[CallerStats]) -> str:
    payload = []
    for stats in ranked:
        row = asdict(stats)
        row.pop("samples", None)
        payload.append(row)
    return json.dumps(payload, indent=2)
