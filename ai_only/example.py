"""Minimal example of the mechanics. The forecasting method is up to your team."""
import os
import re

import ftf

os.environ["FTF_TEST_MODE"] = "1"  # this example only ever sends to the test address
model = ftf.APPROVED_MODELS["DeepSeek V4.1 Flash"]  # any allowed model works; see ai_only/README.md
q = ftf.load_questions()[0]  # A1

notes = ftf.ask(q["id"], "research", f"Summarise recent news relevant to: {q['text']}", model, run=1, online=True)
reply = ftf.ask(q["id"], "final", f"{q['text']}\n\nNotes:\n{notes}\n\nReply with one whole number from 1 to 99.", model, run=1)

answers = ftf.answers_template()
answers[q["id"]] = min(99, max(1, int(re.search(r"\d+", reply).group())))  # naive parsing
for qid, value in answers.items():  # placeholders so the test submission is complete
    if value is None:
        answers[qid] = 50 if qid.startswith("A") else 0
ftf.submit(answers, run=1)
