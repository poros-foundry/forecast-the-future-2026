# AI-only track: quick start

**1. Install** (from the repo folder)

```bash
pip install -r requirements.txt
```

**2. Set your team details.** You'll receive these by email on 1 Nov at 14:00 GMT. `TEAM_NAME` is the name you'd like to see in the results email if you win a prize.

macOS / Linux:
```bash
export OPENROUTER_API_KEY="your-key" TEAM_ID="team-07" SUBMIT_CODE="your-code" TEAM_NAME="Your team name" FTF_TEST_MODE=1
```

Windows PowerShell:
```powershell
$env:OPENROUTER_API_KEY="your-key"; $env:TEAM_ID="team-07"; $env:SUBMIT_CODE="your-code"; $env:TEAM_NAME="Your team name"; $env:FTF_TEST_MODE="1"
```

These settings last until you close the terminal.

**3. Test.** Run `python ai_only/example.py`. It makes two model calls, a dry run and a test submission, and prints a receipt. It only answers A1, so expect warnings about the other 24 questions.

**4. Submit for real.** Set `FTF_TEST_MODE=0` and submit between **12:00 GMT on 1 Nov and 22:00 GMT on 3 Nov**. Only your latest submission counts. Test mode works at any time.

## Rules

- Make every model call with `ftf.ask()` and give it a role. Use `role="final"` for the call that produces each submitted number.
- **Substantive forecasts:** Being close to the market is fine. What fails is a number with no reasoning behind it. For each question, your trace must show the agent's own estimate, the market price it compared against (Part A), and a reason for the final number.
- **Integrity:** Your submission must be one complete run: the last run you made before 22:00, covering all 25 questions from research to final. For each question, the answer must match the last final call. Judges can see every run you made.
- Steer, don't dictate: changing how your agent forecasts is fine; telling it the answer ("set Texas to 55%") is not.
- Use models and web search only through OpenRouter (`online=True` for search). The data pack is allowed, including its scripts in `code/` and `ftf_tools.py`, and so is your own local code. No other external APIs or data sources.
- Your budget is $30 per team. Requests stop when it runs out. Test on a few questions before a full run. Check your remaining credit any time with `credit_left()`. `ask()` prints the cost of each call and warns when less than $10 is left.
- Email a half-page README to events@porosfoundry.ai by 22:00 GMT on 3 Nov, with the subject **FTF US Midterms README [team_id]**. List every data source and tool you used. Your code is optional; a short note on your tools is enough. `ftf.email_readme("path/to/README.md")` opens a ready-to-send draft in your email app.

**Only these models are allowed.** OpenRouter rejects calls to any other model.

| Model | `ask(model=...)` | Rough cost per call |
|---|---|---|
| Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | ~$0.007 |
| Claude Sonnet 5 | `anthropic/claude-sonnet-5` | ~$0.014 |
| Claude Opus 5 | `anthropic/claude-opus-5` | ~$0.035 |
| GPT-5.6 Terra | `openai/gpt-5.6-terra` | ~$0.016 |
| GPT-6 Sol | `openai/gpt-6-sol` | ~$0.014 |
| Gemini 3.8 Flash | `google/gemini-3.8-flash` | ~$0.006 |
| Gemini 4 Argon | `google/gemini-4-argon` | ~$0.014 |
| DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | ~$0.001 |
| DeepSeek V4 Pro 0423 | `deepseek/deepseek-v4-pro` | ~$0.004 |
| Qwen3 235B A22B Instruct 2507 | `qwen/qwen3-235b-a22b-2507` | ~$0.001 |

Costs are rough estimates for a call of about 3,000 tokens in and 800 out, at OpenRouter prices on 28 Oct. `online=True` adds about $0.01–0.02 per call, and models that reason at length can cost several times more.

Some models think before answering, and that thinking counts against `max_tokens`. If replies come back empty or cut off, raise `max_tokens` or cap thinking with `extra_body={"reasoning": {"effort": "low"}}` (Claude models don't accept `"none"`).

## Final replies and submitting

Every `role="final"` reply must end with one line of JSON, with nothing after it. Part A:

```json
{"answer": 62, "own_estimate": 58, "market_reference": 64, "reason": "Polls lean Democratic, but the market prices in late Republican gains."}
```

Part B has no market price to compare against, so leave out `market_reference`:

```json
{"answer": -1.5, "own_estimate": -1.5, "reason": "Futures imply a small fall; we see no reason to move away from them."}
```

`ask()` reads that line (code fences are fine) and prints a warning if it or a field is missing. It still returns the whole reply, so nothing breaks. Ask your model for the line in your final prompt; `example.py` shows one way.

Then build your answers from those lines and check them before sending:

```python
answers = ftf.answers_from_finals(run=3)     # all 25, from the last final call of each question
ftf.submit(answers, run=3, dry_run=True)     # every check, nothing sent
ftf.submit(answers, run=3)                   # the real submission
```

- `answers_from_finals(run)` returns `None` for any question without a usable final answer. Fill those in by rerunning that question, not by typing a number.
- `submit(..., dry_run=True)` runs all the checks and saves the payload in `answers/` without sending it.
- `submit(..., team_name="...")` sets the team name shown in the results. It defaults to your `TEAM_NAME` setting.

**Your git commit.** Every model call is tagged with your git commit, so commit your code before your final run. Uncommitted changes are flagged as dirty. The commit is read from the folder you run from, so run your scripts from inside your repo. If you use your own repo, add `.ftf/`, `answers/` and `receipts/` to its `.gitignore`; otherwise the files the helper writes there flag every later run as dirty.

**The run log.** `ask()` records every call (time, question, role, model, git commit and the final JSON) in `.ftf/runs/<TEAM_ID>-run-<n>.jsonl` in the folder you run from. This lets `submit()` check your run even when your agent and your submission are separate scripts. Run both from the same folder. Research tagged `"general"` counts as research for every question. `ask()` is safe to call from several threads at once; no calls go missing from the log.

**Warnings never block a submission.** Before sending, `submit()` prints a warning if:

- a question has no research call or no final call in this run;
- a submitted value doesn't match that question's last final answer (Part A is compared after rounding, so 62 and 62.0 match);
- the last final call for a question has no answer that can be read;
- it finds no run log for this run, usually because you're submitting from a different folder from the one your agent ran in. It then skips the other checks.

A second final call for the same question also prints a warning when you make it. That's allowed, and the last one counts. Each warning points to something a judge would notice, so fix it if you can, but your answers are sent either way.

## Optional: let the model fetch data with tools

`ftf_tools.py` gives the model three tools built on the data kit: `get_market_odds`, `get_yields` and `get_prices`. They download live data and fall back to the kit's files. Use them, adapt them, or write your own.

```python
import ftf, ftf_tools

messages = [{"role": "user", "content": "Research A9. Use the tools if useful."}]
for _ in range(5):  # cap the rounds
    reply = ftf.ask("A9", "research", messages, model, run=1, tools=ftf_tools.TOOLS, full=True)
    if not reply.tool_calls:
        break
    messages += ftf_tools.handle(reply)
print(reply.content)
```

Each round resends the whole conversation, so keep tool results short. The defaults return summaries; hourly and intraday data can be much longer.

## If submitting fails

- Submit a first version early. Only your latest submission counts, so you can update it until 22:00 GMT.
- `submit()` retries automatically. If it still fails, your answers are saved in `answers/`. Resend them later with `python ai_only/ftf.py resubmit <file>`.
- If the submission server is down at the deadline, email the saved file to events@porosfoundry.ai before 22:00 GMT with the subject **FTF US Midterms submission [team_id]**, for example `FTF US Midterms submission team-07`.
