# Roosterly Support Ticket Agent

## How to run

Use Python 3.11+. Create private `.env` settings from `.env.example` with your keys/email. From the cloned project root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m support_agent           # Run agent; submits decisions
.venv/bin/python -m support_agent.evaluate  # Evaluate only; submits nothing
```

## Decisions

- **Tools:** Python/LangGraph, Pydantic, GPT-5 mini for classification/matching/writing, GPT-6.1 Terra for verification. Codex helped with code/prompts; I reviewed decisions and results.
- **Language:** I did **not use translation**. Models read Dutch, English and German directly. Replies use the customer's language; handoff notes use English. Dutch menu names stay unchanged.
- **Knowledge:** I load the small `docs/faq.md` once as the only answer source; no vector database.
- **Handoff:** Refunds/disputes, cancellations/contract changes, personal-data requests, security incidents, legal threats and threats to leave override FAQ support and spam. Other replies require full FAQ support and configurable confidence **≥0.85**.
- **Defaults:** Empty subject and body close without a model call: `nl`, `other`, `P4`, empty-ticket reason. Nonempty unknown-language tickets hand off with fallback `nl`. Other spam closes using classified category/priority.

## Reliability

I set `MAX_RETRIES=3` in `.env`: one initial attempt plus at most three retries.

- **Rate limit:** I wait 0.21 seconds before each API call to stay below the limit of five requests per second.
- **429 — too many requests:** I wait for the time specified in `Retry-After`, then try again within the retry limit.
- **503 — temporarily unavailable:** I retry with increasing delays, doubling the wait each time, up to three retries.
- **409 — already handled:** I record this and do not submit another action for that ticket.
- **Timeout/connection failure:** I make a GET call to check the ticket's status because the action may have reached the server. I record an unknown outcome and do not blindly resend it.
- **Crash:** On restart, I fetch open tickets again. The server excludes handled tickets and rejects duplicate actions with `409`.
- **Processing failure:** I record a safe error message, leave the ticket unsubmitted, and continue with the next ticket.
- **Security/logs:** Keys stay in `.env`. Customer text is treated as data, not instructions. Logs exclude customer text and generated replies.

## Eval and fix

I compared 10 examples with supplied labels, hidden from the agent. No actions were submitted. Reports: [before](evaluations/20261118T074250927613Z.json), [after](evaluations/20261118T090549549910Z.json).

| Run | Language accuracy | Category accuracy | Priority accuracy | Action accuracy | All four correct | Unnecessary handoffs | Missed reference handoffs | Processing failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline | 100% | 100% | 80% | 60% | 60% | 4 | 0 | 0 |
| Final | 100% | 90% | 70% | 90% | 60% | 1 | 0 | 0 |

**Problem:** Replying when a ticket needs human support can cause costly mistakes. The first run had zero missed reference handoffs, but four unnecessary handoffs. I had given the classifier too much freedom: choosing handoff skipped the FAQ check. Some generated replies also added unsupported details or missed conditions, so the verifier rejected them. Sending these answerable tickets to people works against the agent's goal of reducing manual work.

**Fix:** I used fixed deterministic python routing rules so tickets without a mandatory handoff reach FAQ matching. I also clarified the writing instructions and gave fixable replies one correction attempt using verifier feedback. The corrected reply must pass the same checks; otherwise, it goes to a human. This balances avoiding unsafe replies with reducing unnecessary handoffs. In the final run, unnecessary handoffs fell from four to one, while missed reference handoffs stayed at zero.

**Cost/100 (illustrative):** Assume input/output tokens per ticket: mini 5,000/2,000; Terra 3,000/1,000. Rates/million: [mini](https://developers.openai.com/api/docs/models/gpt-5-mini) $0.25/$2; [Terra](https://developers.openai.com/api/docs/models/gpt-6.1-terra) $1/$5. Calculation: `100 × (5000×0.25 + 2000×2 + 3000×1 + 1000×5) / 1,000,000` ≈ **$1.33**. Actual usage/spend was not recorded.
