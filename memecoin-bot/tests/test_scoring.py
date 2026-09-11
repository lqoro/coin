"""Behavioural tests for the consistency ranking."""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memecoin_bot.models import Callout, Outcome
from memecoin_bot.scoring import rank_callers, score_caller

BASE = datetime(2026, 9, 1, tzinfo=timezone.utc)
ENTRY = 50_000.0


def make(caller: str, multiples: list[float], *, retained: float = 0.4) -> list[Outcome]:
    return [
        Outcome(
            callout=Callout(
                caller=caller,
                mint=f"{caller}{i}",
                called_at=BASE + timedelta(hours=i),
                entry_mcap_usd=ENTRY,
                symbol=f"S{i}",
            ),
            peak_mcap_usd=ENTRY * m,
            mcap_now_usd=ENTRY * m * retained,
        )
        for i, m in enumerate(multiples)
    ]


def test_multiples_derive_from_marketcap():
    outcome = make("a", [4.0], retained=0.25)[0]
    assert outcome.peak_multiple == 4.0
    assert outcome.held_multiple == 1.0
    assert outcome.drawdown_from_peak == 0.75


def test_consistent_caller_beats_one_lucky_moonshot():
    steady = make("steady", [2.5, 3.0, 2.2, 4.0, 2.8, 3.4, 2.1, 5.0])
    lottery = make("lottery", [300.0, 0.1, 0.05, 0.2, 0.1, 0.05, 0.1, 0.15])
    # The lottery caller wins on mean multiple by a mile...
    assert score_caller("lottery", lottery).mean_peak_multiple > \
        score_caller("steady", steady).mean_peak_multiple
    # ...and still loses the ranking, which is the whole point.
    ranked = rank_callers(steady + lottery, min_calls=5)
    assert [s.caller for s in ranked] == ["steady", "lottery"]


def test_call_volume_alone_does_not_win():
    sniper = make("sniper", [3.0] * 8)
    sprayer = make("sprayer", [0.4, 2.1] * 40)
    ranked = rank_callers(sniper + sprayer, min_calls=5)
    assert ranked[0].caller == "sniper"
    assert ranked[1].calls == 80


def test_small_samples_are_shrunk_not_trusted():
    tiny = score_caller("tiny", make("tiny", [4.0, 4.0, 4.0]))
    large = score_caller("large", make("large", [4.0] * 40))
    assert tiny.median_peak_multiple == large.median_peak_multiple
    assert tiny.consistency_score < large.consistency_score


def test_min_calls_filters_thin_records():
    outcomes = make("thin", [10.0, 10.0]) + make("thick", [2.0] * 6)
    assert [s.caller for s in rank_callers(outcomes, min_calls=5)] == ["thick"]


def test_rugs_are_penalised():
    clean = score_caller("clean", make("clean", [1.8] * 10))
    rugged = score_caller("rugged", make("rugged", [1.8] * 5 + [0.02] * 5))
    assert rugged.rug_rate == 0.5
    assert rugged.consistency_score < clean.consistency_score


def test_cli_runs_on_sample_data():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "memecoin_bot.cli",
         "--outcomes", str(root / "data" / "sample_outcomes.jsonl"), "--json", "--top", "1"],
        cwd=root, capture_output=True, text=True, check=True,
    )
    assert '"caller": "steady_sam"' in result.stdout
