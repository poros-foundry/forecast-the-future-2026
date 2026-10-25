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

| Model | `ask(model=...)` | Rough cost per call |
|---|---|---|
| *(to be confirmed)* | | |

## If submitting fails

- Submit a first version early. Only your latest submission counts, so you can update it until 21:00 GMT.
- `submit()` retries automatically. If it still fails, your answers are saved in `answers/`. Resend them later with `python ai_only/ftf.py resubmit <file>`.
- If the submission server is down at the deadline, email the saved file to events@porosfoundry.ai before 21:00 GMT with the subject **FTF US Midterms submission [team_id]**, for example `FTF US Midterms submission team-07`.
