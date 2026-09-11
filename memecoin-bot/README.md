# memecoin-bot

Ranks pump.fun callers by **how consistently their calls work**, not by how
many followers they have or how big their single best call was.

## The ranking question

"Who's the best caller" is usually answered with the wrong statistic. A mean
multiple is owned by the tail: one 400x buried in thirty zeros produces a
better-looking average than eight straight 3x runners, even though only the
second record is followable. This ranks on typical-case measures instead:

| Signal | Column | What it answers |
| --- | --- | --- |
| Geometric mean multiple | `GEO x` | What a *typical* call returns, with the tail compressed |
| Median peak multiple | `MED x` | The middle call, immune to outliers entirely |
| 25th-percentile multiple | `P25 x` | How bad the bad quarter of calls gets |
| 2x hit rate | `2x%` | How often a call actually works |
| Rug rate | `RUG%` | Share of calls that never cleared 0.5x |
| Median drawdown from peak | `DD%` | Whether the peak was real or a one-candle wick |

Two guards sit on top:

- **Shrinkage** — a score is scaled by `n / (n + 5)`, so three good calls read
  as noise rather than a record until the sample grows.
- **`--min-calls`** — callers below the threshold (default 5) are dropped.

Popularity is not an input anywhere. Neither is call volume: spraying a hundred
tickers raises `CALLS` and nothing else.

## Usage

```bash
# Rank an already-priced callout log
python3 -m memecoin_bot.cli --outcomes data/sample_outcomes.jsonl

# Price raw callouts live against pump.fun, then rank
python3 -m memecoin_bot.cli --callouts my_callouts.jsonl --min-calls 8 --top 10

# Machine-readable
python3 -m memecoin_bot.cli --outcomes data/sample_outcomes.jsonl --json
```

Sample output:

```
CALLER                  SCORE    CALLS   MED x    GEO x    P25 x    2x%     5x%     RUG%    DD%
--------------------------------------------------------------------------------------------
steady_sam              27.86    14      2.32     2.32     1.26     57      14      0       70
midcurve_mia            18.36    11      1.74     1.81     1.27     36      9       0       80
volume_vince            8.09     40      0.81     0.75     0.31     22      2       38      67
moonshot_max            3.39     12      0.21     0.57     0.15     17      17      83      69
```

`moonshot_max` has the best single call in that dataset (a 180x) and the
highest mean multiple. He places fourth, which is the intended behaviour.

## Input format

One JSON object per line. For `--callouts`:

```json
{"caller": "@somecaller", "mint": "9xQ...pump", "symbol": "WIF",
 "called_at": "2026-09-01T14:22:00Z", "entry_mcap_usd": 42000, "source": "telegram"}
```

`--outcomes` takes the same fields plus `peak_mcap_usd` and `mcap_now_usd`,
skipping the network entirely.

`entry_mcap_usd` must be the market cap **at the moment of the call** — that
is the number the whole ranking rests on. Taking it from the current cap, or
from whatever the caller claims in their post, silently invalidates every
column in the table.

## Where callouts come from

Ingestion is left to the caller of this library, because the places callers
actually post (Telegram channels, X, Discord) each need their own scraper and
their own credentials. Anything that can emit the JSONL above feeds the
pipeline. Once callouts exist, `sources.resolve_outcomes` prices each mint
against pump.fun's coin and candlestick endpoints, falling back to Dexscreener
for tokens that graduated to Raydium and dropped off the pump.fun index.

Both hosts must be reachable from wherever this runs. In a sandbox with a
restricted egress policy they will fail with `SourceError`, and `--outcomes`
is the offline path.

## Reading the results honestly

- **Post-call market caps are the ceiling, not a fill.** `MED x` is the best
  exit that existed, not one anybody got. `DD%` is there to show how quickly
  that exit closed.
- **Survivorship cuts both ways.** A caller who deletes losing posts will score
  well here. The log is only as honest as its collection.
- **Past consistency is not a forecast.** A caller's edge decays as their
  audience grows; the entry cap they post at stops being the cap you get.

## Tests

```bash
python3 -m pytest tests -q
```

The suite asserts the ranking properties directly: a lucky moonshot loses to a
steady record, volume alone does not win, small samples are shrunk, and rugs
are penalised.
