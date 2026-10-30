# forecast-the-future-2026
US Midterm Election Night Edition: battleground races and the post-election market reaction

This repo is the participant data kit. All times are GMT (UTC). Dates are `YYYY-MM-DD`.

**You are not expected to use any of the data given here, and there are no rules on what you use.** It is provided only to save you time. Your forecasts are evaluated against the real outcomes and compared with the prediction market benchmark. AI-only teams have rules on data and tools; see [`ai_only/README.md`](ai_only/README.md).

## What we provide

**Data (`data/`)**: ready-made files you can use straight away.

| File | What it is | Made by |
|---|---|---|
| `kalshi_odds_hourly.csv` | Hourly Kalshi odds for A1–A15, with bid, ask, volume and open interest | `fetch_kalshi.py` |
| `polymarket_odds_hourly.csv` | Hourly Polymarket odds for A1–A15 | `fetch_polymarket.py` |
| `government_bond_yields_daily.csv` | US 2-year, US 10-year and UK 10-year yields since 2016 (B5–B7) | `fetch_treasury_yields.py` |
| `yahoo_prices_daily.csv` | Daily open, high, low, close, adjusted close and volume since 2016 for SPY, IWM, NVDA, VIX, gold, WTI and Henry Hub | `fetch_yahoo_data.py` |

The official VIX history (daily open, high, low and close since 1990) is on [Cboe's VIX historical data page](https://www.cboe.com/tradable_products/vix/vix_historical_data/), as a CSV at `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`. B4 is scored on Cboe's official close. FRED republishes the same close as `VIXCLS`.

**Code (`code/`)**: scripts that download the same public data fresh, so you can update it yourself. None of them need an API key.

| File | What it does |
|---|---|
| `fetch_kalshi.py` | Downloads hourly Kalshi odds for A1–A15 |
| `fetch_polymarket.py` | Downloads hourly Polymarket odds for A1–A15 |
| `fetch_treasury_yields.py` | Downloads US yields from the US Treasury and the UK gilt yield from the Bank of England |
| `fetch_yahoo_data.py` | Downloads daily or intraday prices from Yahoo Finance |
| `prediction_market_lookup.csv` | The Kalshi and Polymarket market used for each question |

**AI-only track ([`ai_only/`](ai_only/README.md))**: more instructions for AI-only teams, in [`ai_only/README.md`](ai_only/README.md). This folder is only relevant to the AI-only track. It only covers how to call models through OpenRouter and how to submit, and contains no additional information about the questions.

**Additional guide ([`additional_guide.md`](additional_guide.md))**: other free data sources, in case you are looking for somewhere to find more data.

**Databento guide ([`databento_guide.md`](databento_guide.md))**: how to download past election-night futures data from Databento yourself. Because of data licensing, we can't include it in the kit.

**`requirements.txt`**: the Python packages the scripts need.

## Quick start

You need Python 3.11 or later.

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

- US: US Treasury daily par yield curve rates (2-year and 10-year). UK: Bank of England series `IUDMNPY` (10-year nominal par yield). These are the sources used to score B5–B7. FRED republishes the US rates as `DGS2` and `DGS10`.
- US and UK holidays differ, so a blank means that market was closed.
- The US Treasury usually publishes a day's rates the same evening. The Bank of England usually publishes on the next business day, so the latest UK value may be missing.

### Yahoo prices

Columns: `date, instrument, ticker, open, high, low, close, adj_close, volume`, one row per date and instrument.

- `close` is the actual closing price, adjusted only for stock splits. `adj_close` is also adjusted for dividends, so it differs from `close` for SPY, IWM and NVDA and is the one to use for total returns. For futures and VIX the two are the same.
- Because of splits, `close` is not always the price shown on that day. NVDA, for example, has split several times since 2016.
- Gold, WTI and Henry Hub are Yahoo's **front-month** futures. They switch to the next contract as each one expires, so the change on a switch day is not a real move. Part B scores B8–B10 on the **December 2026** contracts.
- VIX has no volume.

**Intraday data.** Yahoo also has intraday prices for recent periods only. Run the script with `--interval`:

| Command | Bar size | How far back |
|---|---|---|
| `python code/fetch_yahoo_data.py --interval 1h` | 1 hour | 730 days (includes the 2024 election until early November 2026) |
| `python code/fetch_yahoo_data.py --interval 5m` | 5 minutes | 60 days |
| `python code/fetch_yahoo_data.py --interval 1m` | 1 minute | 30 days |

Intraday files are saved as `data/yahoo_prices_<interval>.csv`, with times in UTC, and include pre-market and after-hours trading. US stocks don't trade between about 01:00 and 09:00 GMT, so they have no prices overnight.

## Sources

Kalshi and Polymarket public market data; US Treasury; Cboe; Yahoo Finance. Contains Bank of England data.

*Data in this kit is provided for this event only. Please don't share or redistribute it.*
