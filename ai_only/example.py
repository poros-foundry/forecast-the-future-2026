"""Minimal example of the mechanics. The forecasting method is up to your team."""
import os

import ftf

os.environ["FTF_TEST_MODE"] = "1"  # this example only ever sends to the test address
model = ftf.APPROVED_MODELS["DeepSeek V4.1 Flash"]  # any allowed model works; see ai_only/README.md
q = ftf.load_questions()[0]  # A1
run = 1

notes = ftf.ask(q["id"], "research", f"Summarise recent news relevant to: {q['text']}", model, run=run, online=True)
ftf.ask(q["id"], "final", f"""{q['text']}

Notes:
{notes}

Give your own estimate first, then compare it with the market price, then decide.
End your reply with one line of JSON and nothing after it:
{{"answer": <whole number 1-99>, "own_estimate": <your estimate before looking at the market>, "market_reference": <market price used>, "reason": "<one sentence>"}}""", model, run=run)

answers = ftf.answers_from_finals(run)  # the last final call of each question
for qid, value in answers.items():  # placeholders so the test submission is complete
    if value is None:
        answers[qid] = 50 if qid.startswith("A") else 0
# Check first: prints warnings (here, for the 24 placeholder questions) and sends nothing.
ftf.submit(answers, run=run, dry_run=True)
ftf.submit(answers, run=run)
