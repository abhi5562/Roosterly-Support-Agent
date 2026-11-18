import json
from datetime import UTC, datetime
from pathlib import Path


def log_ticket(ticket_id: str, state: dict, api_result: dict):
    classification = state.get("classification")
    faq_match = state.get("faq_match")
    verification = state.get("verification")

    labels = None
    if classification is not None:
        labels = {
            "language": classification.language,
            "category": classification.category,
            "priority": classification.priority,
            "is_spam": classification.is_spam,
            "escalation_intents": classification.escalation_intents,
        }

    faq_ids = []
    if faq_match is not None:
        faq_ids = [
            reference for reference in faq_match.matched_faq_ids
            if reference in state["faq_text"]
        ]

    # Error messages must come from application code, not raw exceptions or responses.
    record = {
        "time": datetime.now(UTC).isoformat(),
        "ticket_id": ticket_id,
        "classification": labels,
        "action": state.get("action"),
        "faq_ids": faq_ids,
        "checks": {
            "faq_fully_supported": faq_match.fully_supported if faq_match is not None else None,
            "faq_confidence": faq_match.confidence if faq_match is not None else None,
            "reply_approved": verification.approved if verification is not None else None,
        },
        "api_outcome": api_result["outcome"],
        "attempts": api_result["attempts"],
        "status_code": api_result["status_code"],
        "error": api_result["error"],
        "ticket_check": api_result.get("ticket_check"),
    }

    directory = Path(__file__).resolve().parent.parent / "logs"
    directory.mkdir(exist_ok=True)
    with (directory / "tickets.jsonl").open("a") as log_file:
        log_file.write(json.dumps(record) + "\n")
