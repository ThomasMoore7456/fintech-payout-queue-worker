import os
import sys
from pathlib import Path

os.environ.setdefault("INFRAI_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from payment_worker import PaymentEvent, decide_action, process_batch


def test_new_creator_payout_is_held_and_audited():
    event = PaymentEvent("pay-7", "creator-2", 2500, "US", 2)
    assert decide_action(event) == "review"

    class FakeClient:
        def __init__(self):
            self.published = []
            self.acked = []

        def publish(self, payload):
            self.published.append(payload)

        def ack(self, message_id):
            self.acked.append(message_id)

    client = FakeClient()
    assert process_batch(client, [{"message_id": "m-1", "payload": event.__dict__}]) == [
        {"payment_id": "pay-7", "creator_id": "creator-2", "action": "review"}
    ]
    assert client.published[0]["action"] == "review"
    assert client.acked == ["m-1"]
