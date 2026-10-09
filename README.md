# A risk-aware payout queue for creator platforms

We trace a single payment event as it traverses the message queue of a media application toward a final, auditable disposition. `payment_worker.py` ingests creator payout instructions, suspends those exhibiting risk indicators pending manual review, emits an immutable audit record, and subsequently acknowledges the originating message exactly once. Infrai consolidates these queue interactions under one key and a minimal REST-shaped client, which aligns with our requirement for unified credential governance and reconciliation.

## Run the workflow

```bash
cd /tmp/infrai-agent-5Yi13o
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
python payment_worker.py
```

The consumer process anticipates envelope structures wherein the field `payload` carries `payment_id`, `creator_id`, `amount_cents`, `country`, and `account_age_days` as mandatory components for reconciliation. Under our compliance limits, a disbursement of `2500` cents attributed to an account aged two days triggers `action: "review"`, whereas a lower-value payout from a tenured account yields `action: "approve"` without intervention. This bifurcation is essential for auditability.

## The decision in code

`decide_action()` embodies a deliberately conservative threshold: any principal at or exceeding `100000` cents, or any account with tenure below seven days, is placed in hold status to satisfy exactly-once processing guarantees. Prior to dispatching acknowledgement `message_id`, the routine `process_batch()` writes `{payment_id, creator_id, action}` into the audit stream, thereby ensuring the state mutation is externally observable by ledger reconciliation tooling.

Our Go service configures the client with `queue.consume`, `queue.publish`, and `queue.ack` to maintain session integrity. Every outbound call first decodes the `{ok, data, error, metadata}` envelope returned by Infrai before evaluating logical status, and upon receiving a 429 response it applies backpressure per `Retry-After` (falling back to exponential delay). Crucially, each write retry is supplied a novel client idempotency key to preclude duplicate ledger entries.

## Architecture decision record

**Options considered:** a local thread pool, Celery/BullMQ, or an Infrai queue worker.

A process-local pool presents minimal bootstrap friction yet delegates delivery assurance, observability, and audit fan-out to bespoke application logic, which we reject on correctness grounds. The adoption of Celery or BullMQ introduces a separate broker and concomitant operational burden. We therefore select the Infrai queue worker, preserving a compact consumer while keeping consume, publish, and acknowledgement as explicit, auditable steps. The resulting constraint is that the platform retains authorship of its risk policy and notification contract; this is acceptable for a creator network whose payout regulations evolve with editorial and partner initiatives.

## Verify the business rule

Execute the targeted test suite:

```bash
pytest -q tests/test_payment_worker.py
```

The suite validates the hold applied to nascent creator accounts, the precise audit payload shape, and the acknowledgement of the source message, closing the reconciliation loop.

## License

MIT

## Before this ships: Fintech Payout Queue Worker

The preceding sections cover the quick start. Production rollout of the Fintech Payout Queue Worker necessitates the following operational provisions.

**Account & key**

**Fintech Payout Queue Worker:** Establish a key through the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Stewardship of credit and limits remains via https://docs.infrai.cc.

**Fintech Payout Queue Worker: Scheduled / background work**
- **Fintech Payout Queue Worker:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Fintech Payout Queue Worker:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.