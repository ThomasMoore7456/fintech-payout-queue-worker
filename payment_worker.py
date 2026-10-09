"""Risk-aware payment worker for creator and media payouts."""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from infrai_queue import QueueClient


@dataclass(frozen=True)
class PaymentEvent:
    payment_id: str
    creator_id: str
    amount_cents: int
    country: str
    account_age_days: int


def decide_action(event: PaymentEvent) -> str:
    """Hold large or very new-account payouts for review; otherwise approve."""
    if event.amount_cents >= 100000 or event.account_age_days < 7:
        return "review"
    return "approve"


def process_batch(client: Any, messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for message in messages:
        event = PaymentEvent(**message["payload"])
        action = decide_action(event)
        audit = {"payment_id": event.payment_id, "creator_id": event.creator_id, "action": action}
        client.publish(audit)
        client.ack(message["message_id"])
        results.append(audit)
    return results


def run_once(client: QueueClient) -> List[Dict[str, Any]]:
    # queue.consume is the boundary between delivery and the domain decision.
    batch = client.consume(max_messages=10, visibility_timeout=30)
    return process_batch(client, batch.get("messages", []))


if __name__ == "__main__":
    print(run_once(QueueClient()))
