# Customer payment recovery and finance re-verification

This checkpoint makes existing gateway verification usable from customer orders
and finance operations. It does not implement provider/bank reconciliation or
real refunds, and does not accept a live-money launch.

## APIs and visibility

`GET /api/v1/payments/orders/{order_id}/attempts/?before={id}` lists only the
owner's attempts. `GET /api/v1/payments/finance/queue/` requires finance_operator
or system_administrator and accepts optional `before`, `status` and `provider`.
Default queue includes created, initiation_unknown, redirected and review_required.
Unknown/repeated filters, invalid enums and nonpositive/out-of-range cursors fail
with 400. Each page has 25 rows plus `has_next`/`next_before`; IDs are descending
and older pages strictly exclude the cursor. Concurrent status changes can move
rows into/out of a filtered queue: this is not a frozen reconciliation report.

Each row separates expected amount, actual capture ledger sum and refund ledger
sum. Amount alone is never presented as received cash. Receipts come from stored
provider references. No callback token, merchant credential fingerprint, address,
phone or card data is returned. Staff rows omit checkout URLs. Owner rows allow
resuming a redirected Zarinpal attempt only for a still-payable order when new
payment capability remains enabled. Late/expired attempts can still be verified
so received funds reach review rather than disappear.

`POST /api/v1/payments/finance/{attempt_id}/verify/` requires CSRF, finance role
and exactly `{"reason": "..."}` (3–500 characters, no NUL). Actor active/staff/
role status is rechecked after its row lock, then locks follow actor → order →
attempt. Existing provider verification runs under these locks. Successful actions
write `payment_reverified` audit in the same transaction as cash/stock effects.
An audit failure rolls back local capture; a subsequent provider 101 can recover.
Repeated completed checks create separate audit actions but never duplicate money.

Customer, callback and staff share the existing 20-check/ten-minute attempt
budget. An outage/timeout does not create a capture. A finance operator cannot
supply an authority, receipt, amount or `paid` flag to override provider evidence.
An unknown/missing authority returns 409 provider_reconciliation_required and
retains its state. Never delete/reject such rows merely to enable another payment.

## UI and redirect checks

Order details show private attempt history, receipt, captured/refunded amounts,
resume links and server verification. Customers may initiate payment for an
existing pending order with no active attempts. Backend ownership/payability,
active-attempt and attempt-count limits always apply. The mounted component keeps
its UUID on ambiguous failure; definitive rejection releases it for a new attempt.
Reload is not a durable offline retry queue; persisted backend attempts still
prevent blind duplicate creation.

Finance panel adds a cursor-paged status queue and reasoned re-verification.
Unknown initiations and received funds needing review are visibly distinct.
There is no manual approve/unblock or refund button for these real payments.
The customer support link includes no confidential payment token.

Checkout and recovery share a redirect helper permitting only the exact fixed
Zarinpal HTTPS host/StartPay path or the existing same-origin development sandbox.
Credentials, alternate hosts/subdomains, extra query/hash and script schemes
are rejected. `npm run test:payments` executes malicious-input boundary checks;
the frontend CI job now includes them. They pass locally; GitHub CI is unexecuted.

## Evidence and remaining work

Eleven behavioral tests cover ownership/privacy, expiry, finance roles/filtering,
exact ledger aggregates, audit/idempotency, audit rollback/101 recovery, unknown
payment guards, two-query bounded owner history, timeout, CSRF/input validation
and post-lock actor revocation. An additional PostgreSQL customer/staff race is
authored and skips locally. TypeScript/build and redirect checks pass; browser
interaction has not been validated here.

Still required: real merchant/SMS credentials and approved templates, provider
sandbox/live pilot, periodic provider/bank reconciliation with explicit binding
for unknown authorities, certified refund/payout flows, operator alerts, legal
policies, PostgreSQL/Redis/HTTPS/browser/load/restore release evidence. These are
not replaced by the queue or by setting ZARINPAL_ENABLED=1.
