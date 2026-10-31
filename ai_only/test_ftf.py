"""Tests for ftf.py, with all network calls mocked. Run: python -m unittest ai_only/test_ftf.py"""
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ftf  # noqa: E402

MODEL = ftf.APPROVED_MODELS["DeepSeek V4.1 Flash"]
ENV = {"OPENROUTER_API_KEY": "test-key", "TEAM_ID": "team-test", "SUBMIT_CODE": "code-123"}


def valid_answers():
    answers = ftf.answers_template()
    for q in answers:
        answers[q] = 50 if q.startswith("A") else -1.5
    return answers


def fake_completion(text="42"):
    response = mock.MagicMock()
    response.choices[0].message.content = text
    response.choices[0].message.tool_calls = None
    response.usage.total_tokens = 10
    return response


def final_line(answer, own=None, market=None, reason="because"):
    fields = {"answer": answer, "own_estimate": answer if own is None else own}
    if market is not None:
        fields["market_reference"] = market
    fields["reason"] = reason
    return "Some reasoning.\n" + json.dumps(fields)


class InTempFolder(unittest.TestCase):
    """Runs each test in an empty folder, with an empty in-memory run log."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        cwd = os.getcwd()
        os.chdir(self.folder.name)
        self.addCleanup(os.chdir, cwd)
        calls = mock.patch.object(ftf, "_calls", [])
        calls.start()
        self.addCleanup(calls.stop)
        credit = mock.patch.object(ftf, "_check_credit")  # no credit lookups from ask()
        self.check_credit = credit.start()
        self.addCleanup(credit.stop)


@mock.patch.dict(os.environ, ENV, clear=True)
class AskTests(InTempFolder):
    def setUp(self):
        super().setUp()
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

    @mock.patch.object(ftf, "GIT_DIRTY", False)
    @mock.patch.object(ftf, "GIT_COMMIT", "abc123")
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
                                         "question": "A3", "role": "final",
                                         "git_commit": "abc123", "git_dirty": False})
        self.assertNotIn("plugins", body)

    def test_full_returns_message_with_tool_calls(self):
        tools = [{"type": "function", "function": {"name": "x", "parameters": {"type": "object", "properties": {}}}}]
        message = ftf.ask("A1", "research", "hi", "some/model", run=1, tools=tools, full=True)
        self.assertIs(message, self.client.chat.completions.create.return_value.choices[0].message)
        self.assertEqual(self.client.chat.completions.create.call_args.kwargs["tools"], tools)

    def test_asks_for_and_prints_cost(self):
        response = fake_completion("42")
        response.usage.cost = 0.01234
        self.client.chat.completions.create.return_value = response
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            ftf.ask("A1", "research", "hi", MODEL, run=1)
        body = self.client.chat.completions.create.call_args.kwargs["extra_body"]
        self.assertEqual(body["usage"], {"include": True})
        self.assertIn("tokens=10 cost=$0.0123", out.getvalue())
        self.check_credit.assert_called_once()

    def test_no_cost_in_response_prints_tokens_only(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            ftf.ask("A1", "research", "hi", MODEL, run=1)  # MagicMock usage has no numeric cost
        self.assertIn("tokens=10\n", out.getvalue())

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
class SubmitTests(InTempFolder):
    def setUp(self):
        super().setUp()
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


class ModelMock(InTempFolder):
    """Mocks OpenRouter; say() sets the next reply and returns it from ask()."""

    def setUp(self):
        super().setUp()
        self.client = mock.MagicMock()
        patcher = mock.patch.object(ftf, "_openrouter", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def say(self, question_id, role, reply, run=1):
        self.client.chat.completions.create.return_value = fake_completion(reply)
        return ftf.ask(question_id, role, "hi", MODEL, run=run)

    def printed(self, fn, *args, **kwargs):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            result = fn(*args, **kwargs)
        return result, out.getvalue()

    def full_run(self, run=1, skip_research=(), skip_final=(), general=False):
        # Research and a final call for every question; finals answer valid_answers().
        if general:
            self.say("general", "research", "notes", run)
        for q, value in valid_answers().items():
            if q not in skip_research and not general:
                self.say(q, "research", "notes", run)
            if q not in skip_final:
                self.say(q, "final", final_line(value, market=55 if q.startswith("A") else None), run)


@mock.patch.dict(os.environ, ENV, clear=True)
class FinalReplyTests(ModelMock):
    def test_valid_json_line(self):
        reply, out = self.printed(self.say, "A1", "final", final_line(62, own=58, market=60))
        self.assertTrue(reply.startswith("Some reasoning."))  # the whole reply is still returned
        self.assertNotIn("Warning", out)
        self.assertEqual(ftf._calls[-1]["final"]["own_estimate"], 58)

    def test_json_inside_code_fences_and_trailing_spaces(self):
        text = 'Reasoning\n```json\n{"answer": 62, "own_estimate": 60, "market_reference": 61, "reason": "x"}   \n```\n  '
        _, out = self.printed(self.say, "A1", "final", text)
        self.assertNotIn("Warning", out)
        self.assertEqual(ftf._calls[-1]["final"]["answer"], 62)

    def test_missing_line_warns_and_returns_reply(self):
        reply, out = self.printed(self.say, "A1", "final", "I think 62.")
        self.assertEqual(reply, "I think 62.")
        self.assertIn("Warning: A1 final reply does not end with a JSON line", out)
        self.assertIsNone(ftf._calls[-1]["final"])

    def test_missing_field_warns(self):
        _, out = self.printed(self.say, "A1", "final", '{"answer": 62, "own_estimate": 60, "reason": "x"}')
        self.assertIn("missing market_reference", out)

    def test_part_b_without_market_reference_is_fine(self):
        _, out = self.printed(self.say, "B1", "final", final_line(-1.5))
        self.assertNotIn("Warning", out)

    def test_other_roles_are_not_parsed(self):
        _, out = self.printed(self.say, "A1", "research", "no json here")
        self.assertNotIn("Warning", out)
        self.assertNotIn("final", ftf._calls[-1])

    def test_second_final_warns_and_last_one_counts(self):
        self.say("A1", "final", final_line(40, market=50))
        _, out = self.printed(self.say, "A1", "final", final_line(45, market=50))
        self.assertIn("second final call for A1", out)
        answers, _ = self.printed(ftf.answers_from_finals, 1)
        self.assertEqual(answers["A1"], 45)

    def test_finals_in_other_runs_are_separate(self):
        self.say("A1", "final", final_line(40, market=50), run=1)
        _, out = self.printed(self.say, "A1", "final", final_line(45, market=50), run=2)
        self.assertNotIn("second final", out)

    def test_answers_from_finals_returns_all_25(self):
        self.say("A1", "final", final_line(62.0, market=50))
        self.say("B2", "final", final_line(-3.25))
        answers, out = self.printed(ftf.answers_from_finals, 1)
        self.assertEqual(list(answers), ftf.QUESTION_IDS)
        self.assertEqual(answers["A1"], 62)
        self.assertIsInstance(answers["A1"], int)
        self.assertEqual(answers["B2"], -3.25)
        self.assertIsNone(answers["A2"])
        self.assertIn("No final answer in run 1 for: A2", out)

    def test_run_log_is_read_back_from_file(self):
        self.say("A1", "research", "notes", run=3)
        self.say("A1", "final", final_line(70, market=65), run=3)
        path = Path(".ftf/runs/team-test-run-3.jsonl")
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)
        ftf._calls.clear()  # as if submit() ran in a separate script
        answers, _ = self.printed(ftf.answers_from_finals, 3)
        self.assertEqual(answers["A1"], 70)
        self.assertEqual([c["role"] for c in ftf.run_calls(3)], ["research", "final"])


@mock.patch.dict(os.environ, ENV, clear=True)
class SubmitCheckTests(ModelMock):
    def dry_run(self, answers=None, run=1, **kwargs):
        with mock.patch.object(ftf.requests, "post") as post_mock:
            result, out = self.printed(ftf.submit, answers or valid_answers(), run, dry_run=True, **kwargs)
        post_mock.assert_not_called()
        return result, out

    def test_complete_run_has_no_warnings(self):
        self.full_run()
        result, out = self.dry_run()
        self.assertEqual(result["warnings"], [])
        self.assertNotIn("Warning", out)

    def test_missing_research(self):
        self.full_run(skip_research=("A2", "B3"))
        result, _ = self.dry_run()
        self.assertEqual(result["warnings"], ["no research call in run 1 for: A2, B3"])

    def test_general_research_counts_for_every_question(self):
        self.full_run(general=True)
        result, _ = self.dry_run()
        self.assertEqual(result["warnings"], [])

    def test_missing_final(self):
        self.full_run(skip_final=("A5",))
        result, _ = self.dry_run()
        self.assertEqual(result["warnings"], ["no final call in run 1 for: A5"])

    def test_value_mismatch(self):
        self.full_run()
        answers = valid_answers()
        answers.update({"A1": 70, "B1": -1.4})
        result, out = self.dry_run(answers)
        self.assertEqual(result["warnings"], [
            "A1: submitting 70, but the last final call in run 1 answered 50",
            "B1: submitting -1.4, but the last final call in run 1 answered -1.5"])
        self.assertIn("never block", out)

    def test_part_a_compared_after_rounding(self):
        self.full_run()
        self.say("A1", "final", final_line(62.0, market=60))
        self.say("A2", "final", final_line(61.6, market=60))
        answers = valid_answers()
        answers.update({"A1": 62, "A2": 62})
        result, _ = self.dry_run(answers)
        self.assertEqual(result["warnings"], [])

    def test_unparseable_last_final(self):
        self.full_run()
        self.say("A3", "final", "My answer is 50.")
        result, _ = self.dry_run()
        self.assertEqual(result["warnings"], ["the last final call has no parseable answer for: A3"])

    def test_no_run_log_gives_one_warning(self):
        result, _ = self.dry_run()
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("run checks were skipped", result["warnings"][0])

    def test_dry_run_saves_payload_with_details(self):
        self.full_run()
        os.environ["TEAM_NAME"] = "The Forecasters"
        result, _ = self.dry_run()
        payload = json.loads(Path(result["saved"]).read_text(encoding="utf-8"))
        self.assertEqual(payload, result["payload"])
        self.assertNotIn("code_commit", payload)  # the commit goes in the model call tags instead
        self.assertEqual(payload["team_name"], "The Forecasters")
        self.assertEqual(payload["helper_version"], ftf.HELPER_VERSION)
        self.assertEqual(payload["run_summary"]["calls_by_role"], {"research": 25, "final": 25})
        self.assertEqual(payload["run_summary"]["models"], [MODEL])
        self.assertEqual(payload["warnings"], [])
        self.assertNotIn("code", payload)
        self.assertEqual(list(Path("answers").glob("answers_*.csv")), [])  # no resend backup for dry runs

    def test_team_name_keyword_overrides_setting(self):
        os.environ["TEAM_NAME"] = "From env"
        result, _ = self.dry_run(team_name="From keyword")
        self.assertEqual(result["payload"]["team_name"], "From keyword")

    def test_dry_run_works_without_submit_code(self):
        del os.environ["SUBMIT_CODE"]
        result, _ = self.dry_run()
        self.assertTrue(result["dry_run"])

    def post_ok(self):
        response = mock.MagicMock(status_code=200)
        response.json.return_value = {"submission_id": "s1"}
        return mock.patch.object(ftf.requests, "post", return_value=response)

    def test_old_usage_sends_only_original_fields_and_saves_payload(self):
        self.full_run()
        with self.post_ok() as post_mock:
            receipt, _ = self.printed(ftf.submit, valid_answers(), 1)
        self.assertEqual(receipt["submission_id"], "s1")
        self.assertEqual(set(post_mock.call_args.kwargs["json"]), {"team", "code", "track", "run", "answers"})
        self.assertEqual(len(list(Path("answers").glob("answers_1_*.csv"))), 1)
        saved = json.loads(next(Path("answers").glob("payload_1_*.json")).read_text(encoding="utf-8"))
        self.assertIn("run_summary", saved)

    def test_details_are_sent_when_enabled(self):
        os.environ["FTF_SEND_DETAILS"] = "1"
        self.full_run()
        with self.post_ok() as post_mock:
            self.printed(ftf.submit, valid_answers(), 1)
        sent = post_mock.call_args.kwargs["json"]
        for field in ("helper_version", "run_summary", "warnings"):
            self.assertIn(field, sent)
        self.assertNotIn("code_commit", sent)

    def test_warnings_never_block_sending(self):
        answers = valid_answers()
        answers["A1"] = 99
        self.full_run()
        with self.post_ok() as post_mock:
            receipt, out = self.printed(ftf.submit, answers, 1)
        self.assertIn("Warning: A1: submitting 99", out)
        self.assertEqual(receipt["submission_id"], "s1")
        post_mock.assert_called_once()


def key_response(usage, limit, remaining):
    response = mock.MagicMock(status_code=200)
    response.json.return_value = {"data": {"usage": usage, "limit": limit, "limit_remaining": remaining}}
    return response


@mock.patch.dict(os.environ, ENV, clear=True)
class CreditTests(unittest.TestCase):
    def setUp(self):
        last = mock.patch.object(ftf, "_last_credit_check", -math.inf)
        last.start()
        self.addCleanup(last.stop)

    def credit_left(self, response):
        with mock.patch.object(ftf.requests, "get", return_value=response) as get, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            remaining = ftf.credit_left()
        return remaining, out.getvalue(), get

    def test_credit_left_prints_and_returns_remaining(self):
        remaining, out, get = self.credit_left(key_response(12.5, 30, 17.5))
        self.assertEqual(remaining, 17.5)
        self.assertIn("Used $12.50 of $30.00, remaining $17.50", out)
        self.assertNotIn("Warning", out)
        self.assertEqual(get.call_args.args[0], "https://openrouter.ai/api/v1/key")
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer test-key"})

    def test_credit_left_warns_below_10(self):
        remaining, out, _ = self.credit_left(key_response(21, 30, 9))
        self.assertEqual(remaining, 9)
        self.assertIn("Warning: less than $10 of credit left", out)

    def test_credit_left_without_a_limit(self):
        remaining, out, _ = self.credit_left(key_response(3, None, None))
        self.assertIsNone(remaining)
        self.assertIn("no spending limit", out)

    def test_credit_left_raises_on_http_error(self):
        response = mock.MagicMock(status_code=401)
        response.raise_for_status.side_effect = requests.HTTPError("401")
        with mock.patch.object(ftf.requests, "get", return_value=response), self.assertRaises(requests.HTTPError):
            ftf.credit_left()

    def check(self, **get_kwargs):
        with mock.patch.object(ftf.requests, "get", **get_kwargs) as get, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            ftf._check_credit()
        return out.getvalue(), get

    def test_ask_check_warns_only_when_low(self):
        out, _ = self.check(return_value=key_response(5, 30, 25))
        self.assertEqual(out, "")
        ftf._last_credit_check = -math.inf
        out, _ = self.check(return_value=key_response(22.5, 30, 7.5))
        self.assertIn("Warning: only $7.50 of credit left", out)

    def test_ask_check_runs_at_most_once_a_minute(self):
        with mock.patch.object(ftf.requests, "get", return_value=key_response(22.5, 30, 7.5)) as get, \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            for _ in range(5):
                ftf._check_credit()
        get.assert_called_once()

    def test_ask_check_never_raises(self):
        out, get = self.check(side_effect=requests.ConnectionError())
        get.assert_called_once()
        self.assertEqual(out, "")


@mock.patch.dict(os.environ, ENV, clear=True)
class ThreadTests(InTempFolder):
    RESEARCH_PER_QUESTION = 15

    def test_ask_from_many_threads_keeps_every_call(self):
        client = mock.MagicMock()
        # Each reply echoes the prompt, so a final call's prompt is its JSON line.
        client.chat.completions.create.side_effect = lambda **kw: fake_completion(kw["messages"][-1]["content"])
        expected = valid_answers()

        def one_question(q):
            for _ in range(self.RESEARCH_PER_QUESTION):
                ftf.ask(q, "research", "notes", MODEL, run=1)
            ftf.ask(q, "final", final_line(expected[q], market=55 if q.startswith("A") else None), MODEL, run=1)

        with mock.patch.object(ftf, "_openrouter", return_value=client), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out, \
                ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(one_question, ftf.QUESTION_IDS))
            answers = ftf.answers_from_finals(1)
        self.assertNotIn("Warning", out.getvalue())

        total = len(ftf.QUESTION_IDS) * (self.RESEARCH_PER_QUESTION + 1)
        self.assertEqual(len(ftf._calls), total)
        logged = ftf.run_calls(1)  # read from the file
        self.assertEqual(len(logged), total)
        self.assertEqual(sorted(c["question"] for c in logged if c["role"] == "final"), sorted(ftf.QUESTION_IDS))
        self.assertEqual(answers, expected)


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class GitStateTests(InTempFolder):
    """Real git repos in a temp folder; ask() is checked with the state they give."""

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "-c", "commit.gpgsign=false", *args], check=True, capture_output=True)

    def make_repo(self):
        self.git("init", "-q")
        Path("agent.py").write_text("print('hi')\n", encoding="utf-8")
        self.git("add", "agent.py")
        self.git("commit", "-q", "-m", "agent")
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

    def ask_with_state(self, state):
        # ask() as it runs after importing ftf in this folder; returns the trace and run log entry.
        client = mock.MagicMock()
        client.chat.completions.create.return_value = fake_completion("notes")
        with mock.patch.dict(os.environ, ENV), mock.patch.object(ftf, "_openrouter", return_value=client), \
                mock.patch.multiple(ftf, GIT_COMMIT=state[0], GIT_DIRTY=state[1]), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(ftf.ask("A1", "research", "hi", MODEL, run=1), "notes")
            trace = client.chat.completions.create.call_args.kwargs["extra_body"]["trace"]
            logged = ftf.run_calls(1)[-1]
        return trace, logged

    def test_clean_commit(self):
        sha = self.make_repo()
        state = ftf._git_state()
        self.assertEqual(state, (sha, False))
        self.assertEqual(len(sha), 40)
        trace, logged = self.ask_with_state(state)
        self.assertEqual((trace["git_commit"], trace["git_dirty"]), (sha, False))
        self.assertEqual((logged["git_commit"], logged["git_dirty"]), (sha, False))

    def test_uncommitted_changes_are_dirty(self):
        sha = self.make_repo()
        Path("agent.py").write_text("print('changed')\n", encoding="utf-8")
        state = ftf._git_state()
        self.assertEqual(state, (sha, True))
        trace, logged = self.ask_with_state(state)
        self.assertEqual((trace["git_commit"], trace["git_dirty"]), (sha, True))
        self.assertEqual((logged["git_commit"], logged["git_dirty"]), (sha, True))

    def test_not_a_git_repo(self):
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(Path.cwd().parent)}):
            state = ftf._git_state()
        self.assertEqual(state, (None, None))
        trace, logged = self.ask_with_state(state)
        self.assertEqual((trace["git_commit"], trace["git_dirty"]), (None, None))
        self.assertEqual((logged["git_commit"], logged["git_dirty"]), (None, None))

    def test_git_not_installed(self):
        with mock.patch.object(ftf.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(ftf._git_state(), (None, None))

    def test_import_warns_once_without_a_commit(self):
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(Path.cwd().parent)}):
            result = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {str(ftf.HERE)!r}); import ftf"],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.count("Warning"), 1)


if __name__ == "__main__":
    unittest.main()
