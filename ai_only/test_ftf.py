"""Tests for ftf.py, with all network calls mocked. Run: python -m unittest ai_only/test_ftf.py"""
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ftf  # noqa: E402

ENV = {"OPENROUTER_API_KEY": "test-key", "TEAM_ID": "team-test", "SUBMIT_CODE": "code-123"}


def valid_answers():
    answers = ftf.answers_template()
    for q in answers:
        answers[q] = 50 if q.startswith("A") else -1.5
    return answers


def fake_completion(text="42"):
    response = mock.MagicMock()
    response.choices[0].message.content = text
    response.usage.total_tokens = 10
    return response


@mock.patch.dict(os.environ, ENV, clear=True)
class AskTests(unittest.TestCase):
    def setUp(self):
        self.client = mock.MagicMock()
        self.client.chat.completions.create.return_value = fake_completion("42")
        patcher = mock.patch.object(ftf, "_openrouter", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rejects_missing_or_invalid_role(self):
        for role in (None, "", "forecaster"):
            with self.assertRaises(ValueError):
                ftf.ask("A1", role, "hi", "some/model", run=1)
        self.client.chat.completions.create.assert_not_called()

    def test_rejects_invalid_question_id(self):
        with self.assertRaises(ValueError):
            ftf.ask("A16", "research", "hi", "some/model", run=1)

    def test_sends_user_session_and_trace(self):
        reply = ftf.ask("A3", "final", "hi", "some/model", run=5, temperature=0)
        self.assertEqual(reply, "42")
        kwargs = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "some/model")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(kwargs["temperature"], 0)
        body = kwargs["extra_body"]
        self.assertEqual(body["user"], "team-test")
        self.assertEqual(body["session_id"], "team-test-run-5")
        self.assertEqual(body["trace"], {"trace_id": "team-test-run-5-A3", "trace_name": "A3",
                                         "question": "A3", "role": "final"})
        self.assertNotIn("plugins", body)

    def test_full_returns_message_with_tool_calls(self):
        tools = [{"type": "function", "function": {"name": "x", "parameters": {"type": "object", "properties": {}}}}]
        message = ftf.ask("A1", "research", "hi", "some/model", run=1, tools=tools, full=True)
        self.assertIs(message, self.client.chat.completions.create.return_value.choices[0].message)
        self.assertEqual(self.client.chat.completions.create.call_args.kwargs["tools"], tools)

    def test_online_adds_web_search(self):
        ftf.ask("general", "research", "hi", "some/model", run=1, online=True)
        body = self.client.chat.completions.create.call_args.kwargs["extra_body"]
        self.assertEqual(body["plugins"], [{"id": "web"}])

    def test_missing_team_id_gives_clear_error(self):
        del os.environ["TEAM_ID"]
        with self.assertRaisesRegex(RuntimeError, "TEAM_ID"):
            ftf.ask("A1", "research", "hi", "some/model", run=1)


class ValidateTests(unittest.TestCase):
    def test_valid_answers_pass(self):
        ftf.validate_answers(valid_answers())

    def test_question_set(self):
        self.assertEqual(len(ftf.QUESTION_IDS), 25)
        self.assertEqual(ftf.QUESTION_IDS[14], "A15")
        self.assertEqual([q["id"] for q in ftf.load_questions()], ftf.QUESTION_IDS)

    def test_reports_missing_and_extra_ids(self):
        answers = valid_answers()
        del answers["A1"], answers["B10"]
        answers["B11"] = 0
        with self.assertRaises(ValueError) as e:
            ftf.validate_answers(answers)
        self.assertIn("missing: A1, B10", str(e.exception))
        self.assertIn("not question IDs: B11", str(e.exception))

    def test_reports_bad_values(self):
        answers = valid_answers()
        answers.update({"A1": 62.5, "A2": 0, "A3": 100, "A4": None, "A5": True,
                        "B1": 26, "B4": -31, "B5": 101, "B6": math.nan, "B7": math.inf})
        with self.assertRaises(ValueError) as e:
            ftf.validate_answers(answers)
        message = str(e.exception)
        for q in ("A1", "A2", "A3", "A4", "A5", "B1", "B4", "B5", "B6", "B7"):
            self.assertIn(f"{q}:", message)
        for q in ("A6", "B2", "B8"):
            self.assertNotIn(f"{q}:", message)

    def test_limits_are_inclusive(self):
        answers = valid_answers()
        answers.update({"A1": 1, "A2": 99, "B1": -25, "B4": 30, "B5": -100})
        ftf.validate_answers(answers)


@mock.patch.dict(os.environ, ENV, clear=True)
class SubmitTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        cwd = os.getcwd()
        os.chdir(self.folder.name)
        self.addCleanup(os.chdir, cwd)
        sleep = mock.patch.object(ftf.time, "sleep")
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def saved_csvs(self):
        return list(Path("answers").glob("answers_*.csv"))

    def test_saves_csv_before_sending_and_saves_receipt(self):
        def post(url, json, timeout):
            self.assertEqual(len(self.saved_csvs()), 1)  # backup exists before sending
            self.assertEqual(json["run"], "team-test-run-1")
            self.assertEqual(json["track"], "ai-only")
            self.assertEqual(json["answers"], valid_answers())
            response = mock.MagicMock(status_code=200)
            response.json.return_value = {"submission_id": "s1", "received_at": "t", "hash": "h"}
            return response

        with mock.patch.object(ftf.requests, "post", side_effect=post) as post_mock:
            receipt = ftf.submit(valid_answers(), run=1)
        self.assertEqual(receipt["submission_id"], "s1")
        self.assertEqual(post_mock.call_args.args[0], ftf.DEFAULT_SUBMIT_URL)
        self.assertEqual(len(list(Path("receipts").glob("receipt_1_*.json"))), 1)

    def test_team_name_is_sent_only_when_set(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {}
        with mock.patch.object(ftf.requests, "post", return_value=response) as post_mock:
            ftf.submit(valid_answers(), run=1)
            self.assertNotIn("team_name", post_mock.call_args.kwargs["json"])
            os.environ["TEAM_NAME"] = "The Forecasters"
            ftf.submit(valid_answers(), run=1)
            self.assertEqual(post_mock.call_args.kwargs["json"]["team_name"], "The Forecasters")

    def test_test_mode_uses_test_address(self):
        os.environ["FTF_TEST_MODE"] = "1"
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {}
        with mock.patch.object(ftf.requests, "post", return_value=response) as post_mock:
            ftf.submit(valid_answers(), run=1)
        self.assertEqual(post_mock.call_args.args[0], ftf.DEFAULT_SUBMIT_URL + "-test")

    def test_unreachable_server_retries_then_keeps_answers(self):
        with mock.patch.object(ftf.requests, "post", side_effect=requests.ConnectionError()) as post_mock:
            result = ftf.submit(valid_answers(), run=2)
        self.assertIn("error", result)
        self.assertEqual(post_mock.call_count, 3)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], list(ftf.RETRY_WAITS))
        self.assertEqual(len(self.saved_csvs()), 1)
        lines = self.saved_csvs()[0].read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "id,value")
        self.assertEqual(len(lines), 26)  # header + 25 answers

    def test_retries_after_server_error_then_succeeds(self):
        ok = mock.MagicMock(status_code=200)
        ok.json.return_value = {"submission_id": "s2"}
        side_effect = [requests.ConnectionError(), mock.MagicMock(status_code=503), ok]
        with mock.patch.object(ftf.requests, "post", side_effect=side_effect) as post_mock:
            receipt = ftf.submit(valid_answers(), run=1)
        self.assertEqual(receipt["submission_id"], "s2")
        self.assertEqual(post_mock.call_count, 3)

    def test_rejected_submission_is_not_retried_and_keeps_answers(self):
        response = mock.MagicMock(status_code=400, text="bad code")
        with mock.patch.object(ftf.requests, "post", return_value=response) as post_mock:
            result = ftf.submit(valid_answers(), run=3)
        self.assertEqual(result["status"], 400)
        self.assertEqual(post_mock.call_count, 1)
        self.assertEqual(len(self.saved_csvs()), 1)

    def test_resubmit_sends_saved_answers_unchanged(self):
        with mock.patch.object(ftf.requests, "post", side_effect=requests.ConnectionError()):
            saved = ftf.submit(valid_answers(), run="final_v2")["saved"]
        ok = mock.MagicMock(status_code=200)
        ok.json.return_value = {"submission_id": "s3"}
        with mock.patch.object(ftf.requests, "post", return_value=ok) as post_mock:
            receipt = ftf.resubmit(saved)
        self.assertEqual(receipt["submission_id"], "s3")
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["answers"], valid_answers())
        self.assertIsInstance(payload["answers"]["A1"], int)
        self.assertEqual(payload["run"], "team-test-run-final_v2")

    def test_resubmit_rejects_other_files(self):
        with self.assertRaises(ValueError):
            ftf.resubmit("my_answers.csv")

    def test_invalid_answers_are_not_sent(self):
        answers = valid_answers()
        answers["A1"] = 150
        with mock.patch.object(ftf.requests, "post") as post_mock:
            with self.assertRaises(ValueError):
                ftf.submit(answers, run=4)
        post_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
