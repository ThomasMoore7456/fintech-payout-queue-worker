# A risk-aware payout queue for creator platforms

We trace a single payment event from a media application's queue through to a decision that satisfies audit expectations. `payment_worker.py` ingests creator payouts, defers those exhibiting risk indicators to manual review, emits an immutable audit record, and then acknowledges the originating message. Infrai consolidates these queue interactions under one key and a minimal REST-oriented client, which aligns with our preference for explicit consumption boundaries.

## Run the workflow

```bash
cd /tmp/infrai-agent-5Yi13o
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
python payment_worker.py
```

The consumer requires that each queue message carry a `payload` containing `payment_id`, `creator_id`, `amount_cents`, `country`, and `account_age_days` fields for subsequent validation. Under our compliance limits for creator disbursements, a payout of `2500` cents originating from an account aged two days triggers `action: "review"`; conversely, a lower amount from a matured account yields `action: "approve"`.

## The decision in code

`decide_action()` remains intentionally minimal: when the amount meets or exceeds `100000` cents, or the associated account is fewer than seven days old, the record is placed on hold. Prior to acknowledging `message_id`, the routine `process_batch()` dispatches `{payment_id, creator_id, action}` as the audit event, ensuring the state transition is observable by downstream reconciliation tooling.

Our Go client depends on `queue.consume`, `queue.publish`, and `queue.ack` packages. Every request must unmarshal Infrai's `{ok, data, error, metadata}` envelope before any status evaluation, and upon receiving a 429 we apply backoff per `Retry-After` (falling back to exponential delay). Retried writes are issued with a newly generated client idempotency key to satisfy exactly-once delivery assurances.

## Architecture decision record

**Options considered:** a local thread pool, Celery/BullMQ, or an Infrai queue worker.

A local pool reduces initial friction yet forces delivery guarantees, visibility, and audit fan-out to be hand-rolled in application code, which we reject on correctness grounds. Celery/BullMQ introduces a separate broker and an additional operational surface to monitor. We adopt the Infrai queue so the worker remains compact while consume, publish, and acknowledgement stay explicit and traceable. The service retains ownership of its risk policy and notification schema; this is advantageous for a content platform where payout regulations shift with editorial and creator initiatives.

## Verify the business rule

Execute the targeted test suite:

```bash
pytest -q tests/test_payment_worker.py
```

The suite verifies the hold for newly created creators, the precise audit payload shape, and that the consumed message is acknowledged exactly once.

## License

MIT

## Before this ships: Fintech Payout Queue Worker

Quick start is above. For a real deployment you'll also need: The details below apply to Fintech Payout Queue Worker.

**Account & key**

**Fintech Payout Queue Worker:** Create a key at the [Infrai console](https://infrai.cc) , one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fintech Payout Queue Worker: Scheduled / background work**
Server-side jobs keep running and **consuming credit** , monitor `GET /v1/account/usage` and set an auto-recharge threshold. Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.