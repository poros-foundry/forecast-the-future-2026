"""Optional data tools for AI-only teams, built on the data kit's fetch scripts.

Pass TOOLS to ftf.ask(..., tools=TOOLS, full=True). When the reply has tool requests,
handle(reply) runs them and returns the messages to add before asking again:

    for _ in range(5):
        reply = ftf.ask("A9", "research", messages, model, run=1, tools=ftf_tools.TOOLS, full=True)
        if not reply.tool_calls:
            break
        messages += ftf_tools.handle(reply)

Every tool downloads live data and falls back to the data kit's files if the source
can't be reached. Results are raw values only, kept short by default to save tokens.
You can also call the functions directly, or ignore this file and write your own tools.
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
import fetch_kalshi  # noqa: E402
import fetch_polymarket  # noqa: E402
import fetch_treasury_yields  # noqa: E402
import fetch_yahoo_data  # noqa: E402

LOOKUP = pd.read_csv(ROOT / "code" / "prediction_market_lookup.csv", dtype=str).set_index("question_id")
INSTRUMENTS = {name: ticker for ticker, name in fetch_yahoo_data.SYMBOLS.items()}
# Most days of data each Yahoo interval may return (Yahoo's own limits).
MAX_DAYS = {"1d": 3650, "1h": 729, "5m": 59, "1m": 7}


def _records(df):
    # NaN -> None so the result is valid JSON.
    return df.astype(object).where(df.notna(), None).to_dict("records")


def get_market_odds(question_id, days=7, hourly=False):
    """Kalshi and Polymarket odds for one Part A question, as probabilities that the Democrat wins."""
    if question_id not in LOOKUP.index:
        raise ValueError(f"question_id must be one of {', '.join(LOOKUP.index)}")
    days = max(1, min(int(days), 30))
    q = LOOKUP.loc[question_id]
    end = int(time.time())
    start = end - days * 86400
    source = "live"
    try:
        kalshi = fetch_kalshi.fill_hourly(fetch_kalshi.hourly_quotes(q.kalshi_ticker, start, end), end)
        poly = fetch_polymarket.fill_hourly(fetch_polymarket.hourly_prices(q.polymarket_slug, start, end), end)
    except Exception:
        source = "data kit files (live download failed)"
        since = datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%d %H:%M")
        kalshi = pd.read_csv(ROOT / "data" / "kalshi_odds_hourly.csv")
        poly = pd.read_csv(ROOT / "data" / "polymarket_odds_hourly.csv")
        kalshi = kalshi[(kalshi.question_id == question_id) & (kalshi.timestamp_utc >= since)]
        poly = poly[(poly.question_id == question_id) & (poly.timestamp_utc >= since)]

    both = kalshi[["timestamp_utc", "yes_bid", "yes_ask", "yes_mid", "spread", "volume", "open_interest"]].merge(
        poly[["timestamp_utc", "yes_price"]].rename(columns={"yes_price": "polymarket_price"}),
        on="timestamp_utc", how="outer").sort_values("timestamp_utc")
    both = both.rename(columns={c: f"kalshi_{c}" for c in ("yes_bid", "yes_ask", "yes_mid", "spread", "volume", "open_interest")})
    result = {"question_id": question_id, "question": q.question, "source": source,
              "latest": _records(both.tail(1))[0] if len(both) else None}
    if hourly:
        result["hourly"] = _records(both)
    else:
        both["date"] = both.timestamp_utc.str[:10]
        result["daily_last_hour"] = _records(both.groupby("date").last().reset_index()[
            ["date", "kalshi_yes_mid", "polymarket_price"]])
        result["kalshi_volume_by_day"] = _records(both.groupby("date").kalshi_volume.sum().reset_index())
    return result


def get_yields(days=30):
    """Daily US 2-year and 10-year (US Treasury) and UK 10-year (Bank of England) yields, in %."""
    days = max(1, min(int(days), 3650))
    start = datetime.now() - timedelta(days=days)
    source = "live"
    try:
        yields = fetch_treasury_yields.us_treasury(start).merge(
            fetch_treasury_yields.bank_of_england(start), on="date", how="outer")
    except Exception:
        source = "data kit file (live download failed)"
        yields = pd.read_csv(ROOT / "data" / "government_bond_yields_daily.csv", parse_dates=["date"])
        yields = yields[yields.date >= start]
    yields = yields.sort_values("date")
    yields["date"] = yields.date.dt.strftime("%Y-%m-%d")
    return {"source": source, "units": "%", "daily": _records(yields)}


def get_prices(instrument, interval="1d", days=None):
    """Open, high, low, close, adjusted close and volume from Yahoo Finance for one instrument."""
    if instrument not in INSTRUMENTS:
        raise ValueError(f"instrument must be one of {', '.join(INSTRUMENTS)}")
    if interval not in MAX_DAYS:
        raise ValueError(f"interval must be one of {', '.join(MAX_DAYS)}")
    days = int(days) if days else (30 if interval == "1d" else 2)
    if not 1 <= days <= MAX_DAYS[interval]:
        raise ValueError(f"days must be between 1 and {MAX_DAYS[interval]} for interval {interval}")
    start = datetime.now(timezone.utc) - timedelta(days=days)
    source = "live"
    try:
        prices = fetch_yahoo_data.yf.download(
            INSTRUMENTS[instrument], start=start, interval=interval, prepost=interval != "1d",
            auto_adjust=False, progress=False, multi_level_index=False)
        if prices.empty:
            raise RuntimeError("no data returned")
    except Exception:
        if interval != "1d":
            raise RuntimeError(f"Yahoo Finance did not return {interval} data for {instrument}")
        source = "data kit file (live download failed)"
        daily = pd.read_csv(ROOT / "data" / "yahoo_prices_daily.csv")
        daily = daily[(daily.instrument == instrument) & (daily.date >= start.strftime("%Y-%m-%d"))]
        prices = daily.set_index("date").drop(columns=["instrument", "ticker"])
    prices = prices.rename(columns=fetch_yahoo_data.COLUMNS)[list(fetch_yahoo_data.COLUMNS.values())].round(4)
    if source == "live":
        index = prices.index.tz_convert("UTC") if prices.index.tz is not None else prices.index
        prices.index = index.strftime("%Y-%m-%d" if interval == "1d" else "%Y-%m-%d %H:%M")
    prices.index.name = "time_utc"
    return {"instrument": instrument, "ticker": INSTRUMENTS[instrument], "interval": interval,
            "source": source, "rows": _records(prices.reset_index())}


FUNCTIONS = {"get_market_odds": get_market_odds, "get_yields": get_yields, "get_prices": get_prices}


def _tool(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required}}}


TOOLS = [
    _tool("get_market_odds",
          "Hourly Kalshi and Polymarket odds for one Part A question, as the probability that the Democrat wins. "
          "Returns the latest hour and one value per day by default, or every hour with hourly=true.",
          {"question_id": {"type": "string", "enum": list(LOOKUP.index)},
           "days": {"type": "integer", "minimum": 1, "maximum": 30, "description": "How many days back (default 7)"},
           "hourly": {"type": "boolean", "description": "Return every hour instead of one value per day (longer)"}},
          ["question_id"]),
    _tool("get_yields",
          "Daily US 2-year and 10-year Treasury yields and the UK 10-year gilt yield, in %. These are the sources "
          "used to score B5-B7.",
          {"days": {"type": "integer", "minimum": 1, "maximum": 3650, "description": "How many days back (default 30)"}},
          []),
    _tool("get_prices",
          "Open, high, low, close, adjusted close and volume from Yahoo Finance. Gold, WTI and Henry Hub are "
          "front-month futures. Intraday intervals cover recent days only.",
          {"instrument": {"type": "string", "enum": list(INSTRUMENTS)},
           "interval": {"type": "string", "enum": list(MAX_DAYS), "description": "Bar size (default 1d)"},
           "days": {"type": "integer", "minimum": 1,
                    "description": "How many days back (default 30 for 1d, 2 for intraday; at most 7 for 1m, 59 for 5m)"}},
          ["instrument"]),
]


def call(name, arguments):
    """Run one tool by name with a dict of arguments and return its result as a JSON string."""
    if name not in FUNCTIONS:
        raise ValueError(f"Unknown tool {name!r}")
    return json.dumps(FUNCTIONS[name](**arguments), default=str)


def handle(message):
    """Run the tool requests in a model reply. Returns the messages to add to the conversation:
    the reply itself, then one result per request. Errors are returned to the model as text."""
    messages = [{"role": "assistant", "content": message.content,
                 "tool_calls": [tc.model_dump() for tc in message.tool_calls]}]
    for tc in message.tool_calls:
        try:
            result = call(tc.function.name, json.loads(tc.function.arguments or "{}"))
        except Exception as e:
            result = json.dumps({"error": f"{e.__class__.__name__}: {e}"})
        print(f"tool {tc.function.name}({tc.function.arguments}) -> {len(result)} characters")
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return messages
