"""Download daily closes from Yahoo Finance for the Part B instruments.

Writes data/yahoo_daily_closes.csv: one row per date, one column per instrument.
No API key needed.

The gold, WTI and Henry Hub columns are Yahoo's front-month futures (GC=F, CL=F,
NG=F). They switch to the next contract as each one expires, so the change on a
switch day is not a real move. The event scores B8-B10 on the December 2026
contracts.

Usage:
    python code/fetch_yahoo_data.py
    python code/fetch_yahoo_data.py --start 2024-01-01
"""
import argparse
import warnings
from pathlib import Path

import yfinance as yf

# yfinance prints pandas deprecation warnings that don't affect the data.
warnings.filterwarnings("ignore", module="yfinance")

DATA = Path(__file__).resolve().parent.parent / "data"   # one folder up from code/, then data/
OUT = DATA / "yahoo_daily_closes.csv"
SYMBOLS = {
    "SPY": "spy",
    "IWM": "iwm",
    "NVDA": "nvda",
    "^VIX": "vix",
    "GC=F": "gold_front_month",
    "CL=F": "wti_front_month",
    "NG=F": "henry_hub_front_month",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2016-01-01", help="first day, YYYY-MM-DD")
    args = parser.parse_args()

    closes = yf.download(list(SYMBOLS), start=args.start, auto_adjust=False, progress=False)["Close"]
    closes = closes.rename(columns=SYMBOLS)[list(SYMBOLS.values())]
    closes.index.name = "date"

    OUT.parent.mkdir(exist_ok=True)
    closes.round(4).to_csv(OUT, date_format="%Y-%m-%d")
    print(f"Saved {len(closes)} days to {OUT}")


if __name__ == "__main__":
    main()
