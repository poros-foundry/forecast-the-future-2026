"""Forecast the Future helper for AI-only teams.

Plumbing only: model calls through OpenRouter with consistent tags, and checked
submissions. It contains no forecasting logic and never changes the numbers you
submit. Setup and rules: ai_only/README.md

Settings come from environment variables:
    OPENROUTER_API_KEY  your team's OpenRouter key
    TEAM_ID             e.g. team-07
    SUBMIT_CODE         your team's submission code
    SUBMIT_URL          optional; defaults to the event's submission address
    FTF_TEST_MODE       set to 1 to send submissions to the test address

To resend answers saved by a failed submission:
    python ai_only/ftf.py resubmit answers/answers_<run>_<time>.csv
"""
import csv
import json
import math
import numbers
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from openai import APIStatusError, OpenAI

OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEFAULT_SUBMIT_URL = "https://submit.porosfoundry.ai/api/submit"
# The models allowed for the event. OpenRouter rejects calls to any other model.
APPROVED_MODELS = {
    "Claude Haiku 4.5": "anthropic/claude-haiku-4.5",
    "Claude Sonnet 5": "anthropic/claude-sonnet-5",
    "Claude Opus 5": "anthropic/claude-opus-5",
    "GPT-5.6 Terra": "openai/gpt-5.6-terra",
    "GPT-6 Sol": "openai/gpt-6-sol",
    "Gemini 3.8 Flash": "google/gemini-3.8-flash",
    "Gemini 4 Argon": "google/gemini-4-argon",
    "DeepSeek V4.1 Flash": "deepseek/deepseek-v4.1-flash",
    "DeepSeek V4 Pro 0423": "deepseek/deepseek-v4-pro",
    "Qwen3 235B A22B Instruct 2507": "qwen/qwen3-235b-a22b-2507",
}
ROLES = ("research", "forecast", "critique", "aggregate", "final", "other")
QUESTION_IDS = [f"A{i}" for i in range(1, 16)] + [f"B{i}" for i in range(1, 11)]
# Largest allowed absolute value for each Part B answer, with its unit.
B_LIMITS = {
    "B1": (25, "%"), "B2": (25, "%"), "B3": (25, "%"), "B4": (30, "points"),
    "B5": (100, "bp"), "B6": (100, "bp"), "B7": (100, "bp"),
    "B8": (25, "%"), "B9": (25, "%"), "B10": (25, "%"),
}
RETRY_WAITS = (5, 15)  # seconds to wait before the 2nd and 3rd submission attempts
HERE = Path(__file__).resolve().parent
_client = None


def _env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set. See ai_only/README.md.")
    return value


def _openrouter():
    global _client
    if _client is None:
        # Retries network errors, rate limits and server errors with backoff; other errors fail at once.
        _client = OpenAI(base_url=OPENROUTER_URL, api_key=_env("OPENROUTER_API_KEY"), max_retries=3)
    return _client


def load_questions(path=HERE / "questions.json"):
    """Return the 25 questions (id, part, text, unit, market_links) in ID order."""
    questions = json.loads(Path(path).read_text(encoding="utf-8"))
    return sorted(questions, key=lambda q: QUESTION_IDS.index(q["id"]))


def ask(question_id, role, messages, model, run, online=False, full=False, **kwargs):
    """Call a model through OpenRouter and return the reply text.

    question_id: a question ID such as "A1", or "general" for calls not tied to one question.
    role: one of ROLES. Use "final" for the call that produces a submitted number.
    messages: a list of chat messages, or a single string for one user message.
    run: a number or short label for this run, e.g. 1.
    online: True to let OpenRouter search the web for this call (costs extra).
    full: True to return the whole reply message instead of its text, including any
        tool requests (message.tool_calls). Use this with tools=...; see ftf_tools.py.
    Other keyword arguments (temperature, max_tokens, tools, ...) are passed to the model.
    """
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}; got {role!r}")
    if question_id not in QUESTION_IDS and question_id != "general":
        raise ValueError(f"question_id must be A1-A15, B1-B10 or 'general'; got {question_id!r}")
    if model not in APPROVED_MODELS.values():
        print(f"Warning: {model} is not an allowed model, so OpenRouter will probably reject it. See ai_only/README.md")
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    team = _env("TEAM_ID")
    session = f"{team}-run-{run}"
    extra_body = {
        "user": team,
        "session_id": session,
        "trace": {"trace_id": f"{session}-{question_id}", "trace_name": question_id,
                  "question": question_id, "role": role},
    }
    if online:
        extra_body["plugins"] = [{"id": "web"}]
    extra_body.update(kwargs.pop("extra_body", {}))

    try:
        response = _openrouter().chat.completions.create(
            model=model, messages=messages, extra_body=extra_body, **kwargs)
    except APIStatusError as e:
        print(f"OpenRouter error {e.status_code}: {e.message}")
        if e.status_code == 402:
            print("Your team's budget may be used up.")
        raise

    tokens = response.usage.total_tokens if response.usage else "?"
    print(f"{datetime.now(timezone.utc):%H:%M:%S} {question_id} {role} {model} tokens={tokens}")
    message = response.choices[0].message
    if full:
        return message
    if message.tool_calls and not message.content:
        print("The model asked to use a tool. Call ask(..., full=True) to get its tool requests.")
    return message.content


def answers_template():
    """Return all 25 question IDs set to None, ready to fill in."""
    return {q: None for q in QUESTION_IDS}


def validate_answers(answers):
    """Raise ValueError listing every problem, or return None if the answers are valid."""
    problems = []
    missing = [q for q in QUESTION_IDS if q not in answers]
    extra = sorted(set(answers) - set(QUESTION_IDS))
    if missing:
        problems.append("missing: " + ", ".join(missing))
    if extra:
        problems.append("not question IDs: " + ", ".join(map(str, extra)))

    for q in QUESTION_IDS:
        if q not in answers:
            continue
        v = answers[q]
        if isinstance(v, bool) or not isinstance(v, numbers.Real):
            problems.append(f"{q}: {v!r} is not a number")
        elif not math.isfinite(v):
            problems.append(f"{q}: {v} is not a finite number")
        elif q.startswith("A"):
            if not isinstance(v, numbers.Integral) or not 1 <= v <= 99:
                problems.append(f"{q}: {v!r} must be a whole number from 1 to 99")
        else:
            limit, unit = B_LIMITS[q]
            if abs(v) > limit:
                problems.append(f"{q}: {v} must be between -{limit} and {limit} ({unit})")

    if problems:
        raise ValueError("Answers are not valid:\n  " + "\n  ".join(problems))


def _plain(value):
    # numpy numbers -> the same value as a plain Python number, so it can be sent as JSON.
    return value.item() if hasattr(value, "item") else value


def submit(answers, run):
    """Check, save and send your answers. Returns the receipt, or an error dict if sending failed.

    Answers are always saved to answers/ (in the folder you run from) before sending.
    If the server can't be reached, it tries twice more before giving up.
    """
    validate_answers(answers)
    team, code = _env("TEAM_ID"), _env("SUBMIT_CODE")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    backup = Path("answers") / f"answers_{run}_{stamp}.csv"
    backup.parent.mkdir(exist_ok=True)
    with open(backup, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "value"])
        writer.writerows((q, answers[q]) for q in QUESTION_IDS)
    print(f"Answers saved to {backup}")

    url = os.environ.get("SUBMIT_URL", DEFAULT_SUBMIT_URL).rstrip("/")
    test_mode = os.environ.get("FTF_TEST_MODE") == "1"
    if test_mode:
        url += "-test"
    payload = {"team": team, "code": code, "track": "ai-only", "run": f"{team}-run-{run}",
               "answers": {q: _plain(answers[q]) for q in QUESTION_IDS}}

    for wait in (0, *RETRY_WAITS):
        if wait:
            print(f"Submission not sent ({reason}). Trying again in {wait} seconds...")
            time.sleep(wait)
        try:
            response = requests.post(url, json=payload, timeout=30)
        except requests.RequestException as e:
            reason = f"could not reach {url} ({e.__class__.__name__})"
            continue
        if response.status_code < 500:
            break
        reason = f"the server returned an error ({response.status_code})"
    else:
        return _fallback(backup, reason, team)

    if response.status_code >= 400:
        print(f"Submission rejected ({response.status_code}): {response.text}")
        print(f"Your answers are saved in {backup}. Fix the problem and submit again.")
        return {"error": response.text, "status": response.status_code, "saved": str(backup)}

    receipt = response.json()
    receipt_path = Path("receipts") / f"receipt_{run}_{stamp}.json"
    receipt_path.parent.mkdir(exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"{'TEST ' if test_mode else ''}Submission received: {receipt.get('submission_id')} "
          f"at {receipt.get('received_at')} (hash {receipt.get('hash')}). Receipt saved to {receipt_path}")
    return receipt


def _fallback(backup, reason, team):
    print(f"Submission not sent: {reason}.")
    print(f"Your answers are saved in {backup}. Resend them later with:")
    print(f"    python ai_only/ftf.py resubmit {backup}")
    print(f"If the submission server is still down at the deadline, email {backup} to events@porosfoundry.ai "
          f"before 21:00 GMT with the subject: FTF US Midterms submission {team}")
    return {"error": reason, "saved": str(backup)}


def resubmit(path):
    """Send answers saved by submit() again, for example after the server couldn't be reached."""
    path = Path(path)
    match = re.fullmatch(r"answers_(.+)_\d{8}T\d{6}Z\.csv", path.name)
    if not match:
        raise ValueError(f"{path.name} is not a file saved by submit() (answers_<run>_<time>.csv)")
    with open(path, newline="", encoding="utf-8") as f:
        answers = {row["id"]: _number(row["value"]) for row in csv.DictReader(f)}
    return submit(answers, match.group(1))


def _number(text):
    try:
        return int(text)
    except ValueError:
        return float(text)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "resubmit":
        resubmit(sys.argv[2])
    else:
        sys.exit("Usage: python ai_only/ftf.py resubmit answers/answers_<run>_<time>.csv")
