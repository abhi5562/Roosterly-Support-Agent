# Roosterly Support Ticket Agent

## How to run

Use Python 3.11+. From a fresh clone:

```bash
git clone https://github.com/abhi5562/Roosterly-Support-Agent.git
cd Roosterly-Support-Agent
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Create `.env` using `.env.example` with both API keys and your candidate email. Then run:

```bash
.venv/bin/python -m support_agent           # Submits decisions
.venv/bin/python -m support_agent.evaluate  # Submits nothing
```

## Decisions

- **Tools:** I used Python, LangGraph and Pydantic. GPT-5 mini reads tickets and writes replies; GPT-6.1 Terra checks them. I reviewed Codex's work against `docs/`.
- **Language:** I did **not translate tickets**. Dutch, English and German are processed directly. Replies use the customer's language; handoff notes use English. Dutch menu names stay unchanged.
- **FAQ:** I kept `docs/faq.md` as the only answer source. It is small enough to load once, so no vector database was needed.
- **Handoff:** Refunds, disputes, cancellations, contract changes, personal-data requests, security incidents, legal threats, threats to leave and P1 tickets go to a human, even when the FAQ helps.
- **Replies:** A reply needs complete FAQ coverage and confidence of **at least 0.85**.
- **Empty tickets:** Blank tickets close without a model call (`nl`, `other`, `P4`). Unknown languages go to a human, with `nl` used only because the API requires a language value.

## Reliability

I set `MAX_RETRIES=3` in `.env` for up to three retries.

- **Rate limit:** A 0.21-second wait before each call keeps requests below five per second.
- **API errors:** For 429, wait for `Retry-After` before retrying; for 503, double the wait with each retry; for 409, record "already handled" and do not resend.
- **Connection failure:** Check the ticket with GET and record `unknown` without resending; the action may already be saved.
- **Crash:** Restart from open tickets; already-handled tickets are excluded by the server.
- **Processing failure:** Log a safe error, skip submission and continue.
- **Security:** Keys stay in `.env`. Customer text is data, not instructions. Logs exclude customer text and generated replies.

## Eval and fix

I compared 10 examples with the supplied answers without showing them to the agent or submitting actions. Reports: [baseline](evaluations/20261118T074250927613Z.json), [after correction](evaluations/20261118T132705567767Z.json).

| Run              | Language accuracy | Category accuracy | Priority accuracy | Action accuracy | Unnecessary handoffs | Missed reference handoffs |
| ---------------- | ----------------: | ----------------: | ----------------: | --------------: | -------------------: | ------------------------: |
| Baseline         |              100% |              100% |               80% |             60% |                    4 |                         0 |
| After correction |              100% |              100% |               80% |             80% |                    2 |                         0 |

**Problem:** The first run missed no reference handoffs, but sent four answerable tickets to humans. The classifier could choose handoff before checking the FAQ, so some questions never reached FAQ matching. Other tickets reached the verifier, but their replies included unsupported details or missed FAQ conditions. These rejections also led to handoffs, adding avoidable work for the support team.

**Fix:** I replaced the classifier's action choice with Python routing rules. Tickets that need a human, including P1 tickets, still go directly to handoff; other actionable tickets reach FAQ matching. I clarified the writing instructions and allowed one correction attempt for fixable replies using verifier feedback. The corrected reply must pass the same checks; another rejection means handoff. In the second evaluation, unnecessary handoffs fell from four to two, with no missed reference handoffs.

**Cost:** I estimated **$0.11245845 ÷ 30 × 100 ≈ $0.37 per 100 tickets** from recorded tokens ([calculation](logs/cost-20261118T135855362997Z.json)).

## What I would improve

- **Speed:** I would process a limited number of tickets in parallel, with a shared rate limiter to stay within five helpdesk requests per second, respect `Retry-After` and account for model API limits.
- **Monitoring:** I would track processing time, model cost and API failures across runs, so I can spot slowdowns, rising costs or reliability problems as ticket volume grows.
- **Client rule:** I would distinguish routine pricing questions from payment or contract problems. The current P2 rule includes anything involving money, which can make simple FAQ questions look urgent. Clearer rules would help the agent assign priorities consistently and keep the support team's urgent queue focused.
