import math
import os
import time

import httpx

from support_agent.models import CloseRequest, HandoffRequest, ReplyRequest


BASE_URL = "https://nakywgkztvzkihdjnwbc.supabase.co/functions/v1/helpdesk/"


class HelpdeskClient:
    def __init__(self):
        api_key = os.environ["HELPDESK_API_KEY"].strip()
        email = os.environ["CANDIDATE_EMAIL"].strip()
        timeout = float(os.environ["REQUEST_TIMEOUT_SECONDS"])
        self.max_retries = int(os.environ["MAX_RETRIES"])
        self.retry_delay = float(os.environ["RETRY_BASE_DELAY_SECONDS"])

        if not api_key or not email:
            raise ValueError("HELPDESK_API_KEY and CANDIDATE_EMAIL must be set.")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be positive and finite.")
        if self.max_retries < 0:
            raise ValueError("MAX_RETRIES must be zero or greater.")
        if not math.isfinite(self.retry_delay) or self.retry_delay <= 0:
            raise ValueError("RETRY_BASE_DELAY_SECONDS must be positive and finite.")

        self.client = httpx.Client(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Candidate-Email": email,
            },
            timeout=timeout,
        )

    def close(self):
        self.client.close()

    def _retry(self, response, attempt):
        if response.status_code not in (429, 503) or attempt == self.max_retries:
            return False

        delay = self.retry_delay * 2**attempt
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is None:
                raise RuntimeError("Helpdesk returned 429 without Retry-After.")
            delay = float(retry_after)
        time.sleep(delay)
        return True

    def _get(self, path, params=None):
        for attempt in range(self.max_retries + 1):
            time.sleep(0.21) # Rate limiting
            response = self.client.get(path, params=params)

            if self._retry(response, attempt):
                continue

            if not response.is_success:
                raise RuntimeError(f"Helpdesk GET failed with HTTP {response.status_code}.")
            try:
                return response.json()
            except ValueError:
                raise RuntimeError("Helpdesk returned invalid JSON.") from None

    def get_status(self):
        return self._get("status")

    def get_ticket(self, ticket_id: str):
        return self._get(f"tickets/{ticket_id}")

    def submit_decision(
        self,
        ticket_id: str,
        request: ReplyRequest | HandoffRequest | CloseRequest,
    ):
        if isinstance(request, ReplyRequest):
            action = "reply"
        elif isinstance(request, HandoffRequest):
            action = "handoff"
        elif isinstance(request, CloseRequest):
            action = "close"
        else:
            raise TypeError("A validated reply, handoff, or close request is required.")

        payload = request.model_dump()
        result = {
            "outcome": "unknown",
            "attempts": 0,
            "status_code": None,
            "error": None,
        }

        for attempt in range(self.max_retries + 1):
            result["attempts"] = attempt + 1
            result["status_code"] = None
            time.sleep(0.21)

            try:
                response = self.client.post(f"tickets/{ticket_id}/{action}", json=payload)
            except httpx.TransportError:
                # The action may have been saved, so check the ticket without resending.
                try:
                    ticket = self.get_ticket(ticket_id)
                    if ticket["handled"] is None:
                        ticket_check = "open"
                    else:
                        ticket_check = "handling_present"
                except (httpx.TransportError, RuntimeError):
                    ticket_check = "failed"

                result["error"] = "Submission outcome is unknown after a transport failure; action was not resent."
                result["ticket_check"] = ticket_check
                return result

            result["status_code"] = response.status_code
            if response.is_success:
                result["outcome"] = "success"
                return result

            if response.status_code == 409:
                result["outcome"] = "already_handled"
                return result

            if self._retry(response, attempt):
                continue

            result["outcome"] = "failed"
            result["error"] = f"Helpdesk action failed with HTTP {response.status_code}."
            return result

    def get_examples(self):
        """Return labelled examples"""
        return self._get("examples")

    def iter_open_tickets(self):
        params = {"limit": 10, "status": "open"}
        while True:
            page = self._get("tickets", params=params)
            yield from page["tickets"]
            cursor = page["next_cursor"]
            if cursor is None:
                return
            params["cursor"] = cursor
