"""Tests for ftf_tools.py, with all network calls mocked. Run: python -m unittest ai_only/test_ftf_tools.py"""
import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ftf_tools  # noqa: E402


def tool_call(name, arguments, id="call_1"):
    function = SimpleNamespace(name=name, arguments=json.dumps(arguments))
    return SimpleNamespace(id=id, function=function,
                           model_dump=lambda: {"id": id, "type": "function",
                                               "function": {"name": name, "arguments": json.dumps(arguments)}})


def hourly_points(hours, value):
    now = int(time.time()) // 3600 * 3600
    return {now - h * 3600: value for h in range(hours)}


class SchemaTests(unittest.TestCase):
    def test_tools_match_functions(self):
        self.assertEqual([t["function"]["name"] for t in ftf_tools.TOOLS], list(ftf_tools.FUNCTIONS))

    def test_question_list_comes_from_lookup(self):
        enum = ftf_tools.TOOLS[0]["function"]["parameters"]["properties"]["question_id"]["enum"]
        self.assertEqual(enum, [f"A{i}" for i in range(1, 16)])


class MarketOddsTests(unittest.TestCase):
    def test_live_summary(self):
        with mock.patch.object(ftf_tools.fetch_kalshi, "hourly_quotes",
                               return_value=hourly_points(48, (0.60, 0.62, 10.0, 500.0))), \
             mock.patch.object(ftf_tools.fetch_polymarket, "hourly_prices", return_value=hourly_points(48, 0.605)):
            result = ftf_tools.get_market_odds("A9", days=2)
        self.assertEqual(result["source"], "live")
        self.assertEqual(result["latest"]["kalshi_yes_mid"], 0.61)
        self.assertEqual(result["latest"]["kalshi_spread"], 0.02)
        self.assertEqual(result["latest"]["polymarket_price"], 0.605)
        self.assertIn("daily_last_hour", result)
        self.assertNotIn("hourly", result)

    def test_hourly_detail(self):
        with mock.patch.object(ftf_tools.fetch_kalshi, "hourly_quotes",
                               return_value=hourly_points(5, (0.6, 0.62, 1.0, 5.0))), \
             mock.patch.object(ftf_tools.fetch_polymarket, "hourly_prices", return_value=hourly_points(5, 0.6)):
            result = ftf_tools.get_market_odds("A1", days=1, hourly=True)
        self.assertEqual(len(result["hourly"]), 5)

    def test_falls_back_to_data_kit(self):
        with mock.patch.object(ftf_tools.fetch_kalshi, "hourly_quotes", side_effect=ConnectionError()):
            result = ftf_tools.get_market_odds("A1", days=30)
        self.assertIn("data kit", result["source"])
        json.dumps(result)  # must be valid JSON

    def test_rejects_unknown_question(self):
        with self.assertRaises(ValueError):
            ftf_tools.get_market_odds("B1")


class YieldsAndPricesTests(unittest.TestCase):
    def test_yields_fall_back_to_data_kit(self):
        with mock.patch.object(ftf_tools.fetch_treasury_yields, "us_treasury", side_effect=ConnectionError()):
            result = ftf_tools.get_yields(days=3650)
        self.assertIn("data kit", result["source"])
        self.assertEqual(set(result["daily"][0]), {"date", "us_2y", "us_10y", "uk_10y"})

    def test_prices_live(self):
        frame = pd.DataFrame({"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Adj Close": [1.4],
                              "Volume": [100]}, index=pd.DatetimeIndex(["2026-10-27"]))
        with mock.patch.object(ftf_tools.fetch_yahoo_data.yf, "download", return_value=frame) as download:
            result = ftf_tools.get_prices("spy")
        self.assertEqual(download.call_args.args[0], "SPY")
        self.assertEqual(result["rows"], [{"time_utc": "2026-10-27", "open": 1.0, "high": 2.0, "low": 0.5,
                                           "close": 1.5, "adj_close": 1.4, "volume": 100}])

    def test_prices_daily_falls_back_to_data_kit(self):
        with mock.patch.object(ftf_tools.fetch_yahoo_data.yf, "download", side_effect=ConnectionError()):
            result = ftf_tools.get_prices("nvda", days=3650)
        self.assertIn("data kit", result["source"])
        self.assertGreater(len(result["rows"]), 100)

    def test_prices_rejects_bad_requests(self):
        for kwargs in ({"instrument": "tsla"}, {"instrument": "spy", "interval": "2h"},
                       {"instrument": "spy", "interval": "1m", "days": 8}):
            with self.assertRaises(ValueError):
                ftf_tools.get_prices(**kwargs)


class HandleTests(unittest.TestCase):
    def test_runs_requests_and_returns_messages(self):
        reply = SimpleNamespace(content=None, tool_calls=[tool_call("get_yields", {"days": 5}, id="c1")])
        with mock.patch.dict(ftf_tools.FUNCTIONS, {"get_yields": lambda days: {"days": days}}):
            messages = ftf_tools.handle(reply)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["tool_calls"][0]["id"], "c1")
        self.assertEqual(messages[1], {"role": "tool", "tool_call_id": "c1", "content": '{"days": 5}'})

    def test_errors_go_back_to_the_model(self):
        reply = SimpleNamespace(content=None, tool_calls=[tool_call("get_weather", {}), tool_call("get_prices", {"instrument": "tsla"}, id="c2")])
        messages = ftf_tools.handle(reply)
        self.assertIn("Unknown tool", json.loads(messages[1]["content"])["error"])
        self.assertIn("instrument must be one of", json.loads(messages[2]["content"])["error"])


if __name__ == "__main__":
    unittest.main()
