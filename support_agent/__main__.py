import json
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.callbacks import UsageMetadataCallbackHandler

from support_agent.api import HelpdeskClient
from support_agent.faq import load_faq
from support_agent.logging import log_ticket
from support_agent.workflow import build_workflow


def main():
    load_dotenv()
    faq_text = load_faq()
    workflow = build_workflow()
    client = HelpdeskClient()
    usage = UsageMetadataCallbackHandler()
    tickets_attempted = 0
    outcomes = {
        "success": 0,
        "already_handled": 0,
        "failed": 0,
        "unknown": 0,
        "processing_failed": 0,
    }

    try:
        # Fetch all pages before actions change the open-ticket list.
        tickets = list(client.iter_open_tickets())
        print(f"Open tickets to process: {len(tickets)}")

        for ticket in tickets:
            tickets_attempted += 1
            ticket_id = ticket["id"]
            state = {"ticket": ticket, "faq_text": faq_text}

            try:
                # Keep completed steps available for logging if a later step fails.
                for update in workflow.stream(state, {"callbacks": [usage]}):
                    for values in update.values():
                        state.update(values)
            except Exception:
                outcomes["processing_failed"] += 1
                log_ticket(ticket_id, state, {
                    "outcome": "failed",
                    "attempts": 0,
                    "status_code": None,
                    "error": "Ticket processing failed; no action was submitted.",
                })
                print(f"{ticket_id}: processing failed; no action submitted")
                continue

            try:
                result = client.submit_decision(ticket_id, state["request"])
            except Exception:
                result = {
                    "outcome": "unknown",
                    "attempts": None,
                    "status_code": None,
                    "error": "Submission did not complete; outcome could not be confirmed.",
                }

            log_ticket(ticket_id, state, result)
            outcomes[result["outcome"]] += 1
            print(f"{ticket_id}: {result['outcome']}")

            if result["status_code"] == 401:
                raise SystemExit("Helpdesk authentication failed; check credentials before rerunning.")
    finally:
        client.close()
        if tickets_attempted:
            summary = {
                "time": datetime.now(UTC).isoformat(),
                "tickets_attempted": tickets_attempted,
                "outcomes": outcomes,
                "token_usage_by_model": usage.usage_metadata,
            }
            directory = Path(__file__).resolve().parent.parent / "logs"
            directory.mkdir(exist_ok=True)
            filename = datetime.now(UTC).strftime("usage-%Y%m%dT%H%M%S%fZ.json")
            path = directory / filename
            with path.open("x") as usage_file:
                json.dump(summary, usage_file, indent=2)
            print(f"Token usage saved to {path}")


if __name__ == "__main__":
    main()
