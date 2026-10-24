"""Download daily US Treasury and UK gilt yields.

Writes data/government_bond_yields_daily.csv with columns
date, us_2y, us_10y, uk_10y (all in %). No API key needed.

Sources, the same ones used to score B5-B7:
- us_2y, us_10y: FRED series DGS2 and DGS10 (market yield on US Treasuries
  at constant maturity), via FRED's CSV download.
- uk_10y: Bank of England series IUDMNPY (10-year nominal par yield), via the
  Bank of England database. Contains Bank of England data.

US and UK holidays differ, so a day open in one market and closed in the other
has a blank in the closed market's column. Both sources usually publish a day's
value on the next business day or later.

Usage:
    python code/fetch_treasury_yields.py
    python code/fetch_treasury_yields.py --start 2024-01-01
"""
import argparse
import io
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv"
BOE = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
DATA = Path(__file__).resolve().parent.parent / "data"   # one folder up from code/, then data/
OUT = DATA / "government_bond_yields_daily.csv"


def fred(start):
    r = requests.get(FRED, params={"id": "DGS2,DGS10"}, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), parse_dates=["observation_date"])
    df = df.rename(columns={"observation_date": "date", "DGS2": "us_2y", "DGS10": "us_10y"})
    df[["us_2y", "us_10y"]] = df[["us_2y", "us_10y"]].apply(pd.to_numeric, errors="coerce")
    return df[df.date >= start].dropna(how="all", subset=["us_2y", "us_10y"])


def bank_of_england(start):
    params = {
        "csv.x": "yes", "SeriesCodes": "IUDMNPY", "UsingCodes": "Y", "CSVF": "TN", "VPD": "Y", "VFD": "N",
        "Datefrom": start.strftime("%d/%b/%Y"), "Dateto": "now",
    }
    # The Bank of England blocks requests that don't look like they come from a browser.
    r = requests.get(BOE, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df["date"] = pd.to_datetime(df["DATE"], format="%d %b %Y")
    return df[["date"]].assign(uk_10y=pd.to_numeric(df["IUDMNPY"], errors="coerce")).dropna()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2016-01-01", help="first day, YYYY-MM-DD")
    args = parser.parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d")

    yields = fred(start).merge(bank_of_england(start), on="date", how="outer").sort_values("date")

    OUT.parent.mkdir(exist_ok=True)
    yields.to_csv(OUT, index=False, date_format="%Y-%m-%d")
    last = yields.iloc[-1]
    print(f"Saved {len(yields)} days to {OUT} (latest {last.date:%Y-%m-%d})")


if __name__ == "__main__":
    main()
