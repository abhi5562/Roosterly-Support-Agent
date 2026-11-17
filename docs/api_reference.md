# Roosterly Helpdesk API — Implementation Reference

This document preserves the **documented API contract** Application policies, graph design, and retry implementation choices belong in [`architecture.md`](architecture.md).

## Base URL and authentication

```text
https://nakywgkztvzkihdjnwbc.supabase.co/functions/v1/helpdesk
```

Required headers on **every** request:

```http
Authorization: Bearer <key supplied separately>
X-Candidate-Email: <same candidate email on every request>
```

Optional once: `X-Candidate-Name: <full name>`. The account is created on the first request; a different candidate email identifies a different account. Keep the key outside the repository, using environment variables and a `.env.example`. JSON POST examples also use `Content-Type: application/json`.

## Endpoints

| Method | Path                                          | Documented purpose                                       |
| ------ | --------------------------------------------- | -------------------------------------------------------- |
| GET    | `/status`                                   | Return account mode and open/handled ticket counts       |
| GET    | `/examples`                                 | Return 10 labelled example tickets with reasoning        |
| GET    | `/tickets?limit=10&cursor=<id>&status=open` | List tickets in current set, paginated                   |
| GET    | `/tickets/{id}`                             | Return one ticket plus how it was handled, if applicable |
| POST   | `/tickets/{id}/reply`                       | Send a customer reply                                    |
| POST   | `/tickets/{id}/handoff`                     | Hand ticket to human support                             |
| POST   | `/tickets/{id}/close`                       | Close without action (spam, empty)                       |
| POST   | `/practice/reset`                           | Reopen all practice tickets                              |

### Ticket listing and pagination

- `status=open` (default): tickets not yet handled; `status=all`: all tickets.
- `limit`: maximum **10** per page; `cursor`: continuation cursor (shown as `<id>` in the reference).
- Continue following response field `next_cursor` until it is `null`.
- The reference does **not** specify the full list response envelope, cursor ordering, or behavior of omitted `limit`.

### Ticket object (documented example)

```json
{
  "id": "T005",
  "received_at": "2026-10-05T09:02:00+00:00",
  "channel": "email",
  "customer_plan": "Basis",
  "subject": "Nieuwe medewerker",
  "body": "Goedemorgen, hoe voeg ik een nieuwe medewerker toe aan ons rooster? ..."
}
```

The example illustrates the fields above; the reference does not provide formal type/nullable definitions beyond the example.

### Labelled example (`GET /examples`)

```json
{
  "id": "E03",
  "subject": "Terugbetaling",
  "body": "We waren in augustus dicht wegens verbouwing. Kunnen we die maand terugkrijgen?",
  "label": {
    "language": "nl",
    "category": "billing",
    "priority": "P2",
    "action": "handoff",
    "reason": "Refund request. Client rule: refunds always go to a human."
  }
}
```

These **10 examples** are separate from the **30 practice tickets**. Decision POSTs for example IDs are not permitted.

## Decision request schema

Use the matching action endpoint; all three actions require the common metadata fields.

| Field            | Required        | Documented values / meaning                                        |
| ---------------- | --------------- | ------------------------------------------------------------------ |
| `language`     | Always          | `nl`, `en`, `de`; language used by customer                  |
| `category`     | Always          | `bug`, `billing`, `feature_request`, `question`, `other` |
| `priority`     | Always          | `P1`, `P2`, `P3`, `P4` (definitions in assignment brief)   |
| `reason`       | Always          | One or two sentences explaining category, priority, action         |
| `draft_reply`  | For `reply`   | Customer-facing answer in customer's language                      |
| `handoff_note` | For `handoff` | Information human support needs, in English                        |
| `confidence`   | Optional        | Number from `0` to `1`                                         |

No action-specific additional fields are documented for `close`. The source does not document exact success response bodies or status codes for successful action POSTs.

### Minimal request examples

```bash
export HELPDESK='https://nakywgkztvzkihdjnwbc.supabase.co/functions/v1/helpdesk'
export KEY='<key from email>'
export ME='<candidate email>'

curl -s -H "Authorization: Bearer $KEY" -H "X-Candidate-Email: $ME" "$HELPDESK/status"
curl -s -H "Authorization: Bearer $KEY" -H "X-Candidate-Email: $ME" "$HELPDESK/examples"
curl -s -H "Authorization: Bearer $KEY" -H "X-Candidate-Email: $ME" "$HELPDESK/tickets?limit=3&status=open"
```

Example `reply` POST (from the source's documented payload pattern):

```bash
curl -s -X POST \
  -H "Authorization: Bearer $KEY" \
  -H "X-Candidate-Email: $ME" \
  -H 'Content-Type: application/json' \
  -d '{"language":"nl","category":"question","priority":"P4","reason":"How-to question answered by FAQ F02. No urgency.","draft_reply":"Hoi Anouk, ga naar Team → Medewerker toevoegen ...","confidence":0.93}' \
  "$HELPDESK/tickets/T005/reply"
```

For `handoff`, POST the required common fields plus `handoff_note` to `/tickets/{id}/handoff`. For `close`, POST the required common fields to `/tickets/{id}/close`. These are schema descriptions, not claims about undocumented response payloads.

## Rate limits, failures, and duplicate handling

| HTTP | Error identifier                  | Documented meaning / behavior                                                   |
| ---- | --------------------------------- | ------------------------------------------------------------------------------- |
| 400  | `invalid_json`, `bad_request` | Malformed request; fix request                                                  |
| 400  | `missing_email`                 | `X-Candidate-Email` absent; add header                                        |
| 401  | `unauthorized`                  | Missing or incorrect key; check credentials                                     |
| 404  | `not_found`                     | Unknown endpoint or ticket not in current set; check ID/path                    |
| 409  | `already_handled`               | Ticket already handled; **do not retry** action                           |
| 422  | `validation_failed`             | Missing/invalid field; `problems` lists validation issues                     |
| 429  | `rate_limited`                  | More than **5 requests/second**; wait `Retry-After` seconds, then retry |
| 503  | `service_unavailable`           | Temporary failure; **nothing was saved**; retry with short backoff        |

Approximately **1 in 20** calls to `/tickets` and to the three ticket-action endpoints deliberately returns `503`.

### Idempotency and duplicate-action behavior

- The helpdesk refuses to answer a customer twice: a repeat action on an already-handled ticket returns **409 `already_handled`**.
- Listing `status=open` omits already-handled tickets.
- `GET /tickets/{id}` returns handling information when a ticket has been handled; its exact handling-field schema is **not documented**.
- No idempotency-key header, client-supplied request ID, or other deduplication contract is documented. Do not assume such a feature exists.
