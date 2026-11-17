import math
import os
import time

import httpx


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

    def _get(self, path, params=None):
        for attempt in range(self.max_retries + 1):
            time.sleep(0.21) # Rate limiting
            response = self.client.get(path, params=params)

            # If rate limiting error or service unavailable error
            if response.status_code in (429, 503) and attempt < self.max_retries:
                delay = self.retry_delay * 2**attempt
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after is None:
                        raise RuntimeError("Helpdesk returned 429 without Retry-After.")
                    delay = float(retry_after)
                time.sleep(delay)
                continue

            if not response.is_success:
                raise RuntimeError(f"Helpdesk GET failed with HTTP {response.status_code}.")
            try:
                return response.json()
            except ValueError:
                raise RuntimeError("Helpdesk returned invalid JSON.") from None

    def get_status(self):
        return self._get("status")

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
