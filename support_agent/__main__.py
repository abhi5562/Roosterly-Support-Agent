from dotenv import load_dotenv

from support_agent.api import HelpdeskClient
from support_agent.faq import load_faq
from support_agent.logging import log_ticket
from support_agent.workflow import build_workflow


def main():
    load_dotenv()
    faq_text = load_faq()
    workflow = build_workflow()
    client = HelpdeskClient()

    try:
        # Fetch all pages before actions change the open-ticket list.
        tickets = list(client.iter_open_tickets())
        print(f"Open tickets to process: {len(tickets)}")

        for ticket in tickets:
            ticket_id = ticket["id"]
            state = {"ticket": ticket, "faq_text": faq_text}

            try:
                # Keep completed steps available for logging if a later step fails.
                for update in workflow.stream(state):
                    for values in update.values():
                        state.update(values)
            except Exception:
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
            print(f"{ticket_id}: {result['outcome']}")

            if result["status_code"] == 401:
                raise SystemExit("Helpdesk authentication failed; check credentials before rerunning.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
