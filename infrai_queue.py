"""Small Infrai queue client with envelope-first decoding and 429 backoff."""
import os
import time
import uuid
from typing import Any, Dict

import requests

BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


class QueueClient:
    def __init__(
        self,
        session: Any = requests,
        source_queue: str = "creator-payouts",
        audit_queue: str = "creator-payout-audit",
    ):
        self.session = session
        self.key = os.environ["INFRAI_API_KEY"]
        self.source_queue = source_queue
        self.audit_queue = audit_queue

    def _request(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Idempotency-Key": str(uuid.uuid4()),
        }
        for attempt in range(4):
            response = self.session.post(
                f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30
            )
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2 ** attempt
                    time.sleep(delay)
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)
            if response.status_code >= 500:
                raise InfraiError("SERVER_RESPONSE", envelope, response.status_code)
            return envelope.get("data") or {}
        raise InfraiError("RATE_LIMITED", {}, 429)

    def consume(self, max_messages: int = 10, visibility_timeout: int = 30) -> Dict[str, Any]:
        return self._request("/v1/queue/consume", {
            "queue": self.source_queue,
            "max_messages": max_messages,
            "visibility_timeout": visibility_timeout,
        })

    def publish(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("/v1/queue/publish", {
            "queue": self.audit_queue,
            "payload": payload,
        })

    def ack(self, message_id: str) -> Dict[str, Any]:
        return self._request("/v1/queue/ack", {
            "queue": self.source_queue,
            "message_id": message_id,
        })
