"""Download prices from Yahoo Finance for the Part B instruments.

Writes data/yahoo_prices_<interval>.csv with one row per time and instrument:
open, high, low, close, adj_close and volume. No API key needed.

close is the actual closing price, adjusted only for stock splits. adj_close is
also adjusted for dividends, so it changes on ex-dividend days and is the one to
use for total returns. For futures and indices (VIX) the two are the same.

The gold, WTI and Henry Hub rows are Yahoo's front-month futures (GC=F, CL=F,
NG=F). They switch to the next contract as each one expires, so the change on a
switch day is not a real move. The event scores B8-B10 on the December 2026
contracts.

Intervals:
    1d  daily, from --start (default 2016-01-01)
    1h  hourly, last 730 days
    5m  5-minute, last 60 days
    1m  1-minute, last 30 days
Intraday data includes pre-market and after-hours trading and is in UTC.

Usage:
    python code/fetch_yahoo_data.py
    python code/fetch_yahoo_data.py --start 2024-01-01
    python code/fetch_yahoo_data.py --interval 5m
"""
import argparse
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

# yfinance prints pandas deprecation warnings that don't affect the data.
warnings.filterwarnings("ignore", module="yfinance")

DATA = Path(__file__).resolve().parent.parent / "data"   # one folder up from code/, then data/
SYMBOLS = {
    "SPY": "spy",
    "IWM": "iwm",
    "NVDA": "nvda",
    "^VIX": "vix",
    "GC=F": "gold_front_month",
    "CL=F": "wti_front_month",
    "NG=F": "henry_hub_front_month",
}
COLUMNS = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Adj Close": "adj_close", "Volume": "volume"}
# How far back Yahoo serves each intraday interval, and how many days one request may cover.
INTRADAY = {"1h": (729, 729), "5m": (59, 59), "1m": (29, 7)}


def download(interval, start):
    options = dict(interval=interval, auto_adjust=False, group_by="ticker", progress=False)
    if interval == "1d":
        return yf.download(list(SYMBOLS), start=start, **options)
    days_back, chunk = INTRADAY[interval]
    end = pd.Timestamp.now(tz="UTC")
    t0 = end - pd.Timedelta(days=days_back)
    parts = []
    while t0 < end:
        t1 = min(t0 + pd.Timedelta(days=chunk), end)
        parts.append(yf.download(list(SYMBOLS), start=t0, end=t1, prepost=True, **options))
        t0 = t1
    prices = pd.concat(parts)
    return prices[~prices.index.duplicated(keep="last")]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", default="1d", choices=["1d", *INTRADAY], help="bar size (default 1d)")
    parser.add_argument("--start", default="2016-01-01", help="first day for daily data, YYYY-MM-DD")
    args = parser.parse_args()

    prices = download(args.interval, args.start)
    if args.interval == "1d":
        prices.index = prices.index.strftime("%Y-%m-%d")
        prices.index.name = "date"
    else:
        prices.index = prices.index.tz_convert("UTC").strftime("%Y-%m-%d %H:%M")
        prices.index.name = "timestamp_utc"

    rows = []
    for ticker, name in SYMBOLS.items():
        x = prices[ticker].rename(columns=COLUMNS)[list(COLUMNS.values())].dropna(subset=["close"])
        x.insert(0, "instrument", name)
        x.insert(1, "ticker", ticker)
        rows.append(x)
    out = pd.concat(rows).round(4)

    path = DATA / f"yahoo_prices_{'daily' if args.interval == '1d' else args.interval}.csv"
    path.parent.mkdir(exist_ok=True)
    out.to_csv(path)
    print(f"Saved {len(out)} rows to {path}")


if __name__ == "__main__":
    main()
