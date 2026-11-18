# Roosterly Support Ticket Agent

## How to run

Use Python 3.11+. Clone the repository and install dependencies:

```bash
git clone https://github.com/abhi5562/Roosterly-Support-Agent.git
cd Roosterly-Support-Agent
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Create a private `.env` in this directory using the settings in `.env.example`. Add your OpenAI API key, helpdesk API key and candidate email. Then run:

```bash
.venv/bin/python -m support_agent           # Run agent; submits decisions
.venv/bin/python -m support_agent.evaluate  # Evaluate only; submits nothing
```

## Decisions

- **Tools:** Python/LangGraph, Pydantic, GPT-5 mini for classification/matching/writing, GPT-6.1 Terra for verification. Codex helped with code/prompts; I reviewed decisions and results.
- **Language:** I did **not use translation**. Models read Dutch, English and German directly. Replies use the customer's language; handoff notes use English. Dutch menu names stay unchanged.
- **Knowledge:** I load the small `docs/faq.md` once as the only answer source; no vector database.
- **Handoff:** Refunds/disputes, cancellations/contract changes, personal-data requests, security incidents, legal threats and threats to leave override FAQ support and spam. Other replies require full FAQ support and configurable confidence **≥0.85**.
- **Defaults:** Empty subject and body close without a model call: `nl`, `other`, `P4`, empty-ticket reason. Nonempty unknown-language tickets hand off with fallback `nl`. Other spam closes using classified category/priority.

**Workflow nodes:**

- **classify:** Identifies language, category, priority, empty content, spam and escalation intents; Python selects the initial route.
- **match_faq:** Finds relevant FAQ information and checks answer coverage and confidence.
- **decide:** Keeps close/handoff decisions or allows a reply only when FAQ support and confidence are sufficient.
- **prepare_request:** Builds the customer reply, English handoff note or close request without submitting it.
- **verify_reply:** Independently checks the draft's accuracy, language and safety, and whether rejection can be corrected.
- **revise_reply:** Uses verifier feedback to correct the draft once, then sends it for verification again.
- **handoff:** Changes a rejected reply to handoff and passes the rejection reason to handoff-note preparation.

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

I compared 10 examples with supplied labels, hidden from the agent. No actions were submitted. Reports: [baseline](evaluations/20261118T074250927613Z.json), [after correction](evaluations/20261118T132705567767Z.json).

| Run              | Language accuracy | Category accuracy | Priority accuracy | Action accuracy | All four correct | Unnecessary handoffs | Missed reference handoffs | Processing failures |
| ---------------- | ----------------: | ----------------: | ----------------: | --------------: | ---------------: | -------------------: | ------------------------: | ------------------: |
| Baseline         |              100% |              100% |               80% |             60% |              60% |                    4 |                         0 |                   0 |
| After correction |              100% |              100% |               80% |             80% |              70% |                    2 |                         0 |                   0 |

**Problem:** Replying when a ticket needs human support can cause costly mistakes. The first run had zero missed reference handoffs, but four unnecessary handoffs. I had given the classifier too much freedom: choosing handoff skipped the FAQ check. Some generated replies also added unsupported details or missed conditions, so the verifier rejected them. Sending these answerable tickets to people works against the agent's goal of reducing manual work.

**Fix:** I used deterministic Python routing rules so tickets without a required handoff reach FAQ matching, while P1 tickets always go to a human. I also clarified the writing instructions and gave fixable replies one correction attempt using verifier feedback. The corrected reply must pass the same checks; otherwise, it goes to a human. The latest run had two unnecessary handoffs, down from four initially, with zero missed reference handoffs.

**Cost/100 (final practice run):**  Using published [mini](https://developers.openai.com/api/docs/models/gpt-5-mini) and [Terra](https://developers.openai.com/api/docs/models/gpt-6.1-terra) prices, their estimated costs were $0.0998432 and $0.01261525. Calculation: `($0.0998432 + $0.01261525) / 30 × 100` ≈ **$0.37 per 100 tickets**. This uses recorded tokens, includes cache reads and assumes 30-minute cache writes; see the [full calculation](logs/cost-20261118T135855362997Z.json).

## What I would improve

- **My next step:** I would evaluate more human-labelled Dutch, English and German tickets, including mixed requests and empty email shells. I would use the results to tune the agent so it does not reply when a human is needed, while also avoiding unnecessary handoffs. I would repeat evaluations to check that this balance is maintained consistently.
- **One rule I would change:** I would ask the client to clarify the priority definitions with examples. Does "many users blocked" mean employees at one customer or a wider outage? Does "money involved" include routine pricing questions, which the reference labels treat as P4? Clearer distinctions would help assign priorities consistently.
