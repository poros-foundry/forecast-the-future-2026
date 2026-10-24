"""Download hourly Polymarket odds for the event questions.

Reads code/prediction_market_lookup.csv and writes data/polymarket_odds_hourly.csv.
No API key needed.

yes_price is Polymarket's hourly price for the "Yes" outcome, as a probability
(0.63 = 63%). Every market in the lookup is the Democratic side, so yes_price is
the market's probability that the Democrat wins.

Polymarket rejects requests covering more than about 15 days, so the history is
downloaded in 14-day windows. Hours with no price carry over the previous
hour's value.

Usage:
    python code/fetch_polymarket.py
    python code/fetch_polymarket.py --start 2026-09-01 --end 2026-11-03
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
CODE = Path(__file__).resolve().parent   # this folder (code/)
DATA = CODE.parent / "data"              # one folder up, then data/
LOOKUP = CODE / "prediction_market_lookup.csv"
OUT = DATA / "polymarket_odds_hourly.csv"
WINDOW = 14 * 86400


def get(url, **params):
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def yes_token(slug):
    markets = get(f"{GAMMA}/markets", slug=slug)
    if not markets:
        raise ValueError(f"No Polymarket market with slug {slug}")
    outcomes = json.loads(markets[0]["outcomes"])
    tokens = json.loads(markets[0]["clobTokenIds"])
    return tokens[outcomes.index("Yes")]


def hourly_prices(slug, start, end):
    token = yes_token(slug)
    points = {}
    t0 = start
    while t0 < end:
        t1 = min(t0 + WINDOW, end)
        data = get(f"{CLOB}/prices-history", market=token, startTs=t0, endTs=t1, fidelity=60)
        for p in data.get("history") or []:
            points[p["t"]] = float(p["p"])
        t0 = t1
    return points


def fill_hourly(points, end):
    s = pd.Series(points).sort_index()
    s.index = pd.to_datetime(s.index, unit="s", utc=True).floor("h")
    s = s[~s.index.duplicated(keep="last")]
    hours = pd.date_range(s.index[0], pd.Timestamp(end, unit="s", tz="UTC").floor("h"), freq="h")
    s = s.reindex(hours)
    return pd.DataFrame({
        "timestamp_utc": hours.strftime("%Y-%m-%d %H:%M"),
        "yes_price": s.ffill().round(4).values,
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

    lookup = pd.read_csv(LOOKUP, dtype=str).dropna(subset=["polymarket_slug"])
    frames = []
    for q in lookup.itertuples():
        points = hourly_prices(q.polymarket_slug, start, end)
        if not points:
            print(f"{q.question_id} {q.polymarket_slug}: no data in this period")
            continue
        df = fill_hourly(points, end)
        df.insert(1, "question_id", q.question_id)
        df.insert(2, "market_id", q.polymarket_slug)
        frames.append(df)
        print(f"{q.question_id}: {len(df)} hours, latest {df.yes_price.iloc[-1]:.3f}")

    OUT.parent.mkdir(exist_ok=True)
    pd.concat(frames).to_csv(OUT, index=False)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
