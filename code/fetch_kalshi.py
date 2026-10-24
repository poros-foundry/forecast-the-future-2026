"""Download hourly Kalshi odds for the event questions.

Reads code/prediction_market_lookup.csv and writes data/kalshi_odds_hourly.csv.
No API key needed.

yes_bid and yes_ask are the best yes bid and best yes ask at the end of each
hour, as probabilities (0.63 = 63%). yes_mid is their average and spread is
yes_ask - yes_bid. Every market in the lookup is the Democratic side, so yes_mid
is the market's probability that the Democrat wins. A wide spread means a thin
market, where the mid is less reliable.

volume is the number of contracts traded in the hour. open_interest is the
number of contracts held at the end of the hour. Each contract pays $1.

Kalshi only returns hours in which something changed. For the other hours the
bid, ask and open interest carry over from the previous hour and volume is 0.

Usage:
    python code/fetch_kalshi.py
    python code/fetch_kalshi.py --start 2026-09-01 --end 2026-11-03
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

API = "https://api.elections.kalshi.com/trade-api/v2"
CODE = Path(__file__).resolve().parent   # this folder (code/)
DATA = CODE.parent / "data"              # one folder up, then data/
LOOKUP = CODE / "prediction_market_lookup.csv"
OUT = DATA / "kalshi_odds_hourly.csv"
MAX_HOURS = 5000  # Kalshi returns at most 5,000 candles per request


def get(path, **params):
    r = requests.get(f"{API}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def series_for(ticker):
    # The candlestick endpoint needs the series ticker, which the market only links to via its event.
    event = get(f"/markets/{ticker}")["market"]["event_ticker"]
    return get(f"/events/{event}")["event"]["series_ticker"]


def close_price(side):
    value = (side or {}).get("close_dollars")
    return float(value) if value not in (None, "") else None


def number(value):
    return float(value) if value not in (None, "") else None


def hourly_quotes(ticker, start, end):
    series = series_for(ticker)
    points = {}
    t0 = start
    while t0 < end:
        t1 = min(t0 + MAX_HOURS * 3600, end)
        data = get(f"/series/{series}/markets/{ticker}/candlesticks",
                   start_ts=t0, end_ts=t1, period_interval=60)
        for c in data.get("candlesticks") or []:
            points[c["end_period_ts"]] = (
                close_price(c.get("yes_bid")), close_price(c.get("yes_ask")),
                number(c.get("volume_fp")), number(c.get("open_interest_fp")),
            )
        t0 = t1
    return points


def fill_hourly(points, end):
    q = pd.DataFrame.from_dict(points, orient="index",
                               columns=["yes_bid", "yes_ask", "volume", "open_interest"]).sort_index()
    q.index = pd.to_datetime(q.index, unit="s", utc=True).floor("h")
    q = q[~q.index.duplicated(keep="last")]
    hours = pd.date_range(q.index[0], pd.Timestamp(end, unit="s", tz="UTC").floor("h"), freq="h")
    q = q.reindex(hours)
    q["volume"] = q.volume.fillna(0)
    q[["yes_bid", "yes_ask", "open_interest"]] = q[["yes_bid", "yes_ask", "open_interest"]].ffill()
    q = q.dropna(subset=["yes_bid", "yes_ask"])
    return pd.DataFrame({
        "timestamp_utc": q.index.strftime("%Y-%m-%d %H:%M"),
        "yes_bid": q.yes_bid.round(4).values,
        "yes_ask": q.yes_ask.round(4).values,
        "yes_mid": ((q.yes_bid + q.yes_ask) / 2).round(4).values,
        "spread": (q.yes_ask - q.yes_bid).round(4).values,
        "volume": q.volume.round(2).values,
        "open_interest": q.open_interest.round(2).values,
    })


def to_ts(date):
    return int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2026-10-01", help="first day, YYYY-MM-DD (UTC)")
    parser.add_argument("--end", help="last day, YYYY-MM-DD (UTC, inclusive); default now")
    args = parser.parse_args()

    start = to_ts(args.start)
    now = int(datetime.now(timezone.utc).timestamp())
    end = min(to_ts(args.end) + 86400, now) if args.end else now

    lookup = pd.read_csv(LOOKUP, dtype=str).dropna(subset=["kalshi_ticker"])
    frames = []
    for q in lookup.itertuples():
        points = hourly_quotes(q.kalshi_ticker, start, end)
        if not points:
            print(f"{q.question_id} {q.kalshi_ticker}: no data in this period")
            continue
        df = fill_hourly(points, end)
        df.insert(1, "question_id", q.question_id)
        df.insert(2, "market_id", q.kalshi_ticker)
        frames.append(df)
        last = df.iloc[-1]
        print(f"{q.question_id} {q.kalshi_ticker}: {len(df)} hours, latest bid {last.yes_bid:.3f} ask {last.yes_ask:.3f}")

    OUT.parent.mkdir(exist_ok=True)
    pd.concat(frames).to_csv(OUT, index=False)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
