# forecast-the-future-2026
US Midterm Election Night Edition: battleground races and the post-election market reaction

This repo is the participant data kit. All times are GMT (UTC). Dates are `YYYY-MM-DD`.

**You are not expected to use any of the data given here, and there are no rules on what you use.** It is provided only to save you time. Your forecasts are evaluated against the real outcomes and compared with the prediction market benchmark.

## What we provide

**Data (`data/`)**: ready-made files you can use straight away.

| File | What it is | Made by |
|---|---|---|
| `kalshi_odds_hourly.csv` | Hourly Kalshi odds for A1–A14, with bid, ask, volume and open interest | `fetch_kalshi.py` |
| `polymarket_odds_hourly.csv` | Hourly Polymarket odds for A1–A14 | `fetch_polymarket.py` |
| `government_bond_yields_daily.csv` | US 2-year, US 10-year and UK 10-year yields since 2016 (B5–B7) | `fetch_treasury_yields.py` |
| `yahoo_daily_closes.csv` | Daily closes since 2016 for SPY, IWM, NVDA, VIX, gold, WTI and Henry Hub | `fetch_yahoo_data.py` |
| `past_election_moves_5min.csv` | How futures moved around the last five US election nights | Provided by us, no script |

**Code (`code/`)**: scripts that download the same public data fresh, so you can update it yourself. None of them need an API key.

| File | What it does |
|---|---|
| `fetch_kalshi.py` | Downloads hourly Kalshi odds for A1–A14 |
| `fetch_polymarket.py` | Downloads hourly Polymarket odds for A1–A14 |
| `fetch_treasury_yields.py` | Downloads US Treasury yields from FRED and the UK gilt yield from the Bank of England |
| `fetch_yahoo_data.py` | Downloads daily closes from Yahoo Finance |
| `prediction_market_lookup.csv` | The Kalshi and Polymarket market used for each question |

**Additional guide ([`additional_guide.md`](additional_guide.md))**: other free data sources, in case you are looking for somewhere to find more data.

**`requirements.txt`**: the Python packages the scripts need.

## Quick start

```bash
pip install -r requirements.txt
python code/fetch_kalshi.py
python code/fetch_polymarket.py
```

That refreshes the prediction market odds in `data/`. The other scripts work the same way:

```bash
python code/fetch_treasury_yields.py
python code/fetch_yahoo_data.py
```

Each script takes `--start YYYY-MM-DD`, and the odds scripts also take `--end`. Run any script with `--help` for details.

## Data details

### Prediction market odds

Columns:
- Kalshi: `timestamp_utc, question_id, market_id, yes_bid, yes_ask, yes_mid, spread, volume, open_interest`
- Polymarket: `timestamp_utc, question_id, market_id, yes_price`

Notes:
- Every market is the **Democratic side**, so the value is the market's probability that the Democrat wins (0.63 = 63%). This matches how Part A questions are asked.
- Kalshi's `yes_bid` and `yes_ask` are the best yes bid and best yes ask at the end of each hour. `yes_mid` is their average and `spread` is `yes_ask - yes_bid`.
- A wide `spread` means a thin market, where the mid is less reliable. Spreads are usually 1 cent (0.01), but in quiet overnight hours they can briefly reach 10 cents or more. The mid can then jump even though nobody's view has changed.
- Kalshi's `volume` is the number of contracts traded in the hour, and `open_interest` is the number held at the end of it. Each contract pays $1. Busy markets have more money behind their prices: the Senate races and control markets trade every hour, while FL-22 and ME-02 trade in about 1 hour in 5.
- Kalshi only reports hours in which something changed. For the other hours, the bid, ask and open interest carry over from the previous hour and `volume` is 0.
- Polymarket's `yes_price` is its hourly price for the "Yes" outcome. Polymarket's history has no bid, ask or volume. Hours with no Polymarket price carry over the previous hour's value.
- The two platforms usually agree within 1–2 percentage points. The event's benchmark for each question is the average of the two.
- The markets used for each question are listed in `code/prediction_market_lookup.csv`.

### Government bond yields

Columns: `date, us_2y, us_10y, uk_10y`, all in %.

- US: FRED series `DGS2` and `DGS10`. UK: Bank of England series `IUDMNPY` (10-year nominal par yield). These are the sources used to score B5–B7.
- US and UK holidays differ, so a blank means that market was closed.
- Both sources publish with a delay of a day or more, so the latest day may be missing.

### Yahoo daily closes

Columns: `date, spy, iwm, nvda, vix, gold_front_month, wti_front_month, henry_hub_front_month`.

- Gold, WTI and Henry Hub are Yahoo's **front-month** futures. They switch to the next contract as each one expires, so the change on a switch day is not a real move. Part B scores B8–B10 on the **December 2026** contracts.
- Use these for past daily moves, for example around previous election days.

### Past election moves

Columns: `election, instrument, contract, time_gmt, minutes_from_reference, change_pct, approx_yield_change_bp`.

- Futures: S&P 500 (ES), 2-year Treasury (ZT), 10-year Treasury (ZN), gold (GC), WTI (CL) and Henry Hub (NG), in 5-minute steps.
- Elections: 2016, 2018, 2020, 2022 and 2024. Each window runs from 00:00 GMT the day before election day to 24:00 GMT the day after.
- `change_pct` is the % change from 21:00 GMT on election day. Each election uses that year's December contract.
- `approx_yield_change_bp` is a rough conversion for ZT and ZN only. Treasury futures **rise when yields fall**.
- Futures pause for a daily break around 22:00–23:00 GMT, which shows as gaps.

## Sources

Kalshi and Polymarket public market data; FRED (series `DGS2`, `DGS10`); Yahoo Finance. Contains Bank of England data.

*Data in this kit is provided for this event only. Please don't share or redistribute it.*
