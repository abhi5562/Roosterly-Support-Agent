# Support Ticket Agent — Architecture

This document explains how I plan to build the agent. The requirements are in [`requirements.md`](requirements.md), and the API details are in [`api_reference.md`](api_reference.md).

## Technology and boundaries

- **Python** for the application. One command will run the agent, and another will run the evaluation.
- **LangGraph** to manage the steps and decide which step runs next. Safety checks will be regular Python code inside the workflow, not separate agents.
- **GPT-5 mini** for classifying tickets, finding relevant FAQ entries, writing replies, and preparing handoff notes. It will work directly with Dutch, English, and German tickets, without translating them into English first.
- **GPT-5.6** to check customer replies before they are sent. This check runs only for replies, not for tickets that will be closed or handed off.
- **Pydantic** to check the format and allowed values of model outputs and API requests.
- **`faq.md`** as the only source for customer answers. The FAQ is small, so I won't use a vector database.
- A separate API client for fetching tickets, sending decisions, handling errors, and staying within the rate limit. Final results will be saved as JSONL records in `logs/`.

* Environment variables are loaded from a local .env file.
* API keys, model names, confidence threshold, timeout, and retry settings are stored in .env

| Variable                       | Purpose                                                        |
| ------------------------------ | -------------------------------------------------------------- |
| `OPENAI_API_KEY`             | API key used to access OpenAI models                           |
| `OPENAI_AGENT_MODEL`         | Model for classification, FAQ matching, and content generation |
| `OPENAI_VERIFIER_MODEL`      | Model for independently verifying customer replies             |
| `HELPDESK_API_KEY`           | API key for the Roosterly helpdesk                             |
| `CANDIDATE_EMAIL`            | Email address used to identify the helpdesk account            |
| `REPLY_CONFIDENCE_THRESHOLD` | Minimum confidence required before replying to a customer      |
| `REQUEST_TIMEOUT_SECONDS`    | Maximum time to wait for an API response                       |
| `MAX_RETRIES`                | Maximum number of retries for temporary API failures           |
| `RETRY_BASE_DELAY_SECONDS`   | Initial delay used for retry backoff                           |

## Components and workflow

LangGraph will pass ticket details and results between steps. The shared state will hold the ticket, any handoff flag, classification, matched FAQ entries, proposed and final action, generated text, verification result, API result, and safe error details. Each step will use this state to decide what happens next.

### 1. Fetch tickets

- Fetch open tickets in pages of up to 10. Keep following `next_cursor` until it is `null`.
- The API's open-ticket list tells us what still needs work. After a restart, fetch it again instead of relying on the local logs.
- Never send decisions for tickets from `GET /examples`.

### 2. Early safety checks — Python only

- If **both subject and body are empty**, close the ticket without calling the LLM. Use `language: "nl"` only because the API requires a language value. Include the other required fields and explain that the ticket was empty.
- Check for clear cases that must go to a human: refunds or disputed charges, cancellations or contract changes, GDPR/AVG requests, security incidents, legal threats, and customers threatening to leave.
- For these cases, lock the action to `handoff`, but still run classification so the API gets the required category, priority, and reason.
- For the first version, keep these checks rule-based as planned. We can improve detection of less obvious wording after the initial implementation.

### 3. Classify the ticket — GPT-5 mini

- Read the original subject and body without translating them first.
- Return the language (`nl`, `en`, `de`), category, priority (`P1`–`P4`), spam flag, proposed action, and reason.
- Use Pydantic to check the result. Follow the priority definitions from the assignment.
- The model can suggest an action, but it cannot override a required handoff or the later safety checks.
- If classification fails or is unclear, hand off when a valid API request can be made.

### 4. Match the FAQ

* Load only FAQ entries F01–F12 for customer answers. GPT-5 mini will match questions to the relevant English FAQ text, even when the ticket is in Dutch or German.
* The FAQ contains only customer-answer information. Safety and escalation rules are documented in requirements.md and implemented through the workflow checks.
* Keep the matched FAQ IDs and supporting text for the next steps.
* Reply only when the FAQ contains enough information to answer the whole question. A high confidence score alone is not enough.
* Keep Dutch app menu names exactly as written in the FAQ, even in English or German replies.
* If the FAQ does not cover the question, hand it off.

### 5. Decide the action — Python checks

Apply these rules in order:

1. If an earlier check locked the ticket to `handoff`, keep that action.
2. Allow `close` only for completely empty tickets or clear spam. Otherwise, change a suggested close to `handoff`.
3. Allow `reply` only when the FAQ fully supports it **and** confidence meets the configured threshold.
4. Hand off anything unclear, unsupported, or unsafe.

The confidence threshold is still to be chosen. It will be a project setting, not an API rule, and it will never override a required handoff.

### 6. Write the reply or handoff note

- For `reply`, GPT-5 mini writes in the customer's language using only the matched FAQ information. Dutch menu names stay unchanged.
- For `handoff`, GPT-5 mini writes a short note **in English** explaining the issue and why a human needs to handle it.
- Add a short `reason` explaining the category, priority, and action. Check the required fields with Pydantic.
- Do not include payment details in replies or handoff notes.

### 7. Check replies before sending

- Python checks the API fields, allowed language, Dutch menu names, payment details, and whether the reply has FAQ support.
- For reply candidates only, make a **separate GPT-5.6 call** with its own prompt and structured result. Give it the original ticket, matched FAQ text, and draft reply. It checks whether the answer is correct, in the right language, and free of unsupported claims.
- This check does not translate the ticket into English first.
- If a check fails, change the action to `handoff`, write an English note, and validate the new request.
- The second model is an extra check, not a guarantee. Python safety rules still take priority.

### 8. Send decisions and handle API errors

- Send one action (`reply`, `handoff`, or `close`) to the matching API endpoint.
- Stay within **5 requests per second**.
- For `429`, wait for the time in `Retry-After`. For `503`, retry after a short delay, with a limit on attempts. These limits will be configurable.
- For `409 already_handled`, stop. Do not send another action.
- If a request times out or the connection drops, call `GET /tickets/{id}` first to check whether the action went through. The API reference does not show the full response format, so we need to inspect it before relying on specific fields. If the result is still unclear, don't resend blindly; log it as unresolved.
- For `400` or `422`, fix the request. For `401`, check credentials. For `404`, check the endpoint or ticket ID. Do not keep retrying an unchanged request.
- After a crash, fetch open tickets again. Tickets already handled by the server should no longer appear. If a `409` still occurs, treat it as already handled.

### 9. Logging

- Write **one JSONL record per ticket-processing attempt**, after retries and any API checks finish, or when the result is declared unresolved.
- Record the time, ticket ID, classification (when available), action, FAQ IDs, check results, API outcome (`success`, `already_handled`, `failed`, or `unknown`), number of attempts, and safe error details.
- Never log payment details, API keys, or raw sensitive customer text. Do not mark failed or uncertain requests as successful.
- If the program crashes before writing a log, the next run will still use the API's open-ticket list. A later run may create another log record for the same ticket.

## Evaluation

- Use a **separate evaluation command** to fetch the 10 labelled tickets from `GET /examples` and run the same classification and decision steps **without sending actions**.
- Compare the agent's language, category, priority, and action against the provided labels. Also review FAQ support and reply language. The model being tested must not create its own correct labels.
- Save the first results, find one mistake, fix it, and run the evaluation again. Show the before-and-after results.
- Estimate the model cost per 100 tickets using actual usage and stated pricing assumptions.
- The final practice run is separate: reset the 30 practice tickets, then run the agent once over all open tickets.

## Empty tickets and unknown language

- **Both fields empty:** Close directly, without an LLM call. Use `nl` as a technical fallback for the required API field, not as a detected language.
- **Only one field empty:** Process the text that is available.
- **Non-empty ticket with unknown language:** Choose **`handoff` and write the handoff note in English. Use** **`language: "nl"` as a technical fallback because the API requires** **`nl`,** **`en`, or** `de`. This does not mean the customer wrote in Dutch.

## Checks before implementation

- Confirm access to GPT-5 mini and GPT-5.6 and their exact API model IDs.
- Choose and configure the confidence threshold, request timeouts, and retry limits.
- Inspect the actual `GET /tickets/{id}` response to find a reliable way to check whether a ticket was already handled.
