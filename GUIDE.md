# Guide: other data sources

The kit covers the data the questions are scored on. If you want to look further, the free sources below are a starting point. They are listed for convenience, not as recommendations, and you can use any other public source.

## Macro and interest rates

- **[FRED](https://fred.stlouisfed.org/)**: US and international economic and financial series. Any series downloads as a CSV without an API key, for example `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10`. See [Downloading data from FRED](https://fred.stlouisfed.org/help/data/downloading/using-the-download-data-link/).
- **[US Treasury daily yield curve](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve)**: US Treasury yields across maturities, usually published the same day, a day before they appear on FRED.
- **[Bank of England database](https://www.bankofengland.co.uk/boeapps/database/)**: UK interest rates, including gilt yields. `code/fetch_treasury_yields.py` shows how to download a series.
- **[CME FedWatch](https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html)**: market-implied probabilities of Federal Reserve rate decisions (web page only).

## Market prices

- **[Yahoo Finance via `yfinance`](https://ranaroussi.github.io/yfinance/)**: daily prices for stocks, ETFs, indices and futures. To add tickers, edit `SYMBOLS` in `code/fetch_yahoo_data.py`.

## Elections

- **[MIT Election Data and Science Lab](https://electionlab.mit.edu/data)**: past US election results by race.
- **[FEC bulk data](https://www.fec.gov/data/browse-data/?tab=bulk-data)**: campaign finance filings. Bulk downloads need no key; the API needs a free key.
- **Polling**: [RealClearPolling](https://www.realclearpolling.com/), [Silver Bulletin](https://www.natesilver.net/).
- **Race ratings**: [Cook Political Report](https://www.cookpolitical.com/), [Sabato's Crystal Ball](https://centerforpolitics.org/crystalball/), [Inside Elections](https://insideelections.com/).

Some of these sites need a subscription for part of their content. Check each source's terms before sharing its data.
