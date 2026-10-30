# Databento guide: past election-night market data

Because of data licensing, we can't distribute Databento data in a ready-to-download format. If you need more market data, you can download it directly from [Databento](https://databento.com) with your own account.

**AI-only teams:** Databento isn't allowed for your track. Use only the data pack and models and web search through OpenRouter; see [`ai_only/README.md`](ai_only/README.md).

**Past election nights at intraday detail:**
- **2024:** hourly prices from Yahoo Finance, with `python code/fetch_yahoo_data.py --interval 1h`. Only available until about 4 November 2026, when it drops out of Yahoo's 730-day window.
- **2016, 2018, 2020, 2022 and 2024:** minute-by-minute futures prices from Databento (CME, from 2010). The steps below show how to [set up Databento](#set-a-spending-limit-first) and [download the data](#download). US stocks on Nasdaq are available from 2018.

## Set a spending limit first

**Set a spending limit on Databento's billing page before making any requests.**

- New accounts get **$125 in free credits**. They're deducted automatically from your end-of-month balance; you don't need to activate them.
- Anything beyond $125 is charged to your card. The spending limit includes your credits, so **set it to $125 to avoid any charges**.
- You can also disable usage-based spending on the billing page, and check what a request will cost before running it with `metadata.get_cost`.

## Download

```bash
pip install databento
```

```python
import databento as db

client = db.Historical("YOUR_API_KEY")
request = dict(dataset="GLBX.MDP3", schema="ohlcv-1m", stype_in="raw_symbol",
               symbols=["ESZ6", "ZNZ6"], start="2016-11-07T00:00", end="2016-11-10T00:00")
print(client.metadata.get_cost(**request))  # cost in US dollars; check before downloading
bars = client.timeseries.get_range(**request).to_df()
```

## What to request

Futures use the **December contract** of each election year. The last digit of the symbol is the year, so `ESZ6` is December 2016 in a 2016 request. Times are UTC; `end` is exclusive.

| Election | `start` | `end` | Futures symbols (`GLBX.MDP3`) |
|---|---|---|---|
| 2016 | 2016-11-07T00:00 | 2016-11-10T00:00 | `ESZ6 ZTZ6 ZNZ6 GCZ6 CLZ6 NGZ6` |
| 2018 | 2018-11-05T00:00 | 2018-11-08T00:00 | `ESZ8 RTYZ8 ZTZ8 ZNZ8 GCZ8 CLZ8 NGZ8` |
| 2020 | 2020-11-02T00:00 | 2020-11-05T00:00 | `ESZ0 RTYZ0 ZTZ0 ZNZ0 GCZ0 CLZ0 NGZ0` |
| 2022 | 2022-11-07T00:00 | 2022-11-10T00:00 | `ESZ2 RTYZ2 ZTZ2 ZNZ2 GCZ2 CLZ2 NGZ2` |
| 2024 | 2024-11-04T00:00 | 2024-11-07T00:00 | `ESZ4 RTYZ4 ZTZ4 ZNZ4 GCZ4 CLZ4 NGZ4` |

ES = S&P 500, RTY = Russell 2000 (CME from 2017), ZT = 2-year Treasury, ZN = 10-year Treasury, GC = gold, CL = WTI, NG = Henry Hub. Treasury futures **rise when yields fall**.

For US stocks (SPY, IWM, NVDA), use dataset `XNAS.ITCH` with the plain ticker, for 2018 onwards. It covers trades on Nasdaq only, and there is no trading between about 01:00 and 09:00 GMT, when most results come in.

Each year, 21:00 GMT on election day is 16:00 in New York, the US stock market close.
