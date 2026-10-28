# AI-only track: quick start

**1. Install** (from the repo folder)

```bash
pip install -r requirements.txt
```

**2. Set your team details.** You'll receive these by email on Mon 2 Nov.

macOS / Linux:
```bash
export OPENROUTER_API_KEY="your-key" TEAM_ID="team-07" SUBMIT_CODE="your-code" FTF_TEST_MODE=1
```

Windows PowerShell:
```powershell
$env:OPENROUTER_API_KEY="your-key"; $env:TEAM_ID="team-07"; $env:SUBMIT_CODE="your-code"; $env:FTF_TEST_MODE="1"
```

These settings last until you close the terminal.

**3. Test.** Run `python ai_only/example.py`. It makes two model calls and a test submission, and prints a receipt.

**4. Submit for real.** Set `FTF_TEST_MODE=0` and submit between **16:00 and 21:00 GMT on 3 Nov**. Only your latest submission counts.

## Rules

- Make every model call with `ftf.ask()` and give it a role. Use `role="final"` for the call that produces each submitted number.
- Use models and web search only through OpenRouter. The data kit and your own local code are allowed.
- Your budget is $30 per team. Test on a few questions before a full run.

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

- Submit a first version early. Only your latest submission counts, so you can update it until 21:00 GMT.
- `submit()` retries automatically. If it still fails, your answers are saved in `answers/`. Resend them later with `python ai_only/ftf.py resubmit <file>`.
- If the submission server is down at the deadline, email the saved file to events@porosfoundry.ai before 21:00 GMT with the subject **FTF US Midterms submission [team_id]**, for example `FTF US Midterms submission team-07`.
