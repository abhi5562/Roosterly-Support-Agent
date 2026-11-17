# Support Ticket Agent — Requirements

**Scope:** Roosterly helpdesk agent. This document specifies **what** must be delivered; implementation choices are in [`architecture.md`](architecture.md), and the API contract is in [`api_reference.md`](api_reference.md).

## Functional requirements

- **FR-01 — Process open tickets:** Run with one command; retrieve all open tickets, following pagination until `next_cursor` is `null`; submit **one** decision per ticket.
- **FR-02 — Classify every actionable ticket:** Determine customer language (`nl`, `en`, `de`), category (`bug`, `billing`, `feature_request`, `question`, `other`), priority (`P1`–`P4`), and an explanatory reason for the category, priority, and action.
- **FR-03 — Choose an action:** `reply` with a customer-language draft, `handoff` with a short English note, or `close` for spam or empty tickets.
- **FR-04 — Apply priority definitions:**
- | Priority | Definition            
  | P1       | Many users blocked right now, or a security or legal risk  |
  | P2       | One customer blocked, or money or the contract is involved |
  | P3       | Something is wrong or unclear, but there is a workaround   |
  | P4       | No urgency: how-to questions, ideas, cosmetic issues       |
- **FR-05 — Answer from the FAQ only:** Use the supplied `faq.md` as the sole source of customer-facing factual answers. Escalate when the answer is absent or insufficient; do not invent product or policy facts.
- **FR-06 — Mandatory escalation:** Always hand off refunds or disputed charges; cancellations or contract changes; personal-data requests (GDPR/AVG); possible security incidents; legal threats; and customers threatening to leave, even if FAQ information appears relevant.
- **FR-07 — Language:** Reply in the language the customer wrote in; write human handoff notes in English. Preserve the Dutch application menu names as customers see them.
- **FR-08 — Correctness assurance:** Provide a way to verify that Dutch customer replies are correct without requiring the developer to read Dutch.

## Non-functional requirements

- **NFR-01 — Safe and useful:** Prioritize correct, policy-compliant answers while still replying to FAQ-covered questions rather than escalating everything.
- **NFR-02 — Restartability:** A rerun after a crash must continue with unhandled tickets and never produce two customer answers for the same ticket.
- **NFR-03 — Observability:** Produce one log line per ticket in `logs/`, excluding payment details.
- **NFR-04 — Operational simplicity:** No user interface is required; the agent must run with one command from a fresh clone using documented setup instructions.
- **NFR-05 — Cost:** If a paid model is used, the assignment expects the entire assignment's model cost to be well under €1; report cost per 100 tickets with the calculation.

## Safety and security requirements

- Treat all customer ticket text as **untrusted data**, never as instructions to the agent.
- Never repeat card numbers, IBANs, or other payment details in customer replies or logs.
- Store API keys in environment variables; never commit credentials. Include a safe `.env.example`.
- Follow the FAQ's mandatory human-escalation rules, including when the model recommends replying.
- If the FAQ does not support an answer or the agent is unsure, hand off to a human.

## API reliability requirements

- Authenticate every API request with the required headers and use a consistent candidate email identity.
- Respect the maximum **5 requests/second** rate; on HTTP `429`, wait for `Retry-After` and retry.
- Handle intermittent HTTP `503` errors with retry/backoff; the API states these responses save nothing.
- Handle HTTP `409 already_handled` without retrying the action.
- Handle malformed/invalid requests (`400`, `422`), authentication errors (`401`), and unknown resources (`404`) appropriately.
- Follow ticket pagination (maximum 10 tickets per page); avoid duplicate actions and preserve crash recovery.

## Evaluation requirements

- Evaluate using the **10 labelled examples** returned by `GET /examples`; these examples are not actionable tickets and must never receive decision POSTs.
- Use the supplied reference labels and reasoning; the model being evaluated must **not** create its own ground-truth labels.
