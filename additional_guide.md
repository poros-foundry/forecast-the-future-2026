# Additional guide: other data sources

We list these sources only in case you are looking for somewhere to find additional data. You don't need to use any of them. They are not recommendations, and you can use any other source you like.

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
- **[US House election statistics](https://history.house.gov/Institution/Election-Statistics/Election-Statistics/)**: official results of US House and Senate elections since 1920, from the Clerk of the House.
- **[State election offices](https://www.eac.gov/voters/register-and-vote-in-your-state)**: links to each state's election office, which publishes candidate lists and official results. Directory from the US Election Assistance Commission.
- **[US Census Bureau data](https://data.census.gov/)**: population and demographic data by state and congressional district.

Check each source's terms before sharing its data.
