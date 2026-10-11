# Support write retry safety

Delivered on the development branch; this is not live chat or milestone acceptance.

## Contract

The customer ticket creation/reply and staff reply/routing POST endpoints accept
an optional `request_key` containing a UUID. Existing clients without a key keep
their previous behavior. The support UI now sends a key and retains it in memory
when a submission fails, reusing it only for an unchanged payload on the same
form. An edited payload receives a new key. A reload loses that in-memory retry
key, so this is not a durable offline submission queue.

A key belongs to the authenticated actor across all four endpoints. An identical
retry returns the original success HTTP status, `replayed: true`, and the ticket's
**current** representation (newest 20 visible messages; follow the history cursor for older messages). It does not restore an earlier status or assignment,
append a message, notify the customer again, or duplicate an audit. Customer
representations always exclude internal notes. Changing the endpoint or any
payload field with that key returns `409 idempotency_conflict`. JSON object key
order is ignored; changed whitespace in string values is considered a changed
payload. Explicit malformed/null keys return 400. Only successful writes consume
a key. New unkeyed submissions remain potentially duplicative.

## Transactions and authorization

Writes acquire the actor row lock before ticket locks. Active-account state and
staff support-role eligibility are rechecked after that lock, including before
replay. Message, status, audit, in-app notification and receipt are committed in
one database transaction. Exceptions roll back all of them. A staff member who
loses their role cannot replay a prior staff write. Customer keys cannot retrieve
another customer's receipt or ticket. CSRF enforcement remains on every write.

Receipts store actor, UUID, SHA-256 payload/endpoint digest, ticket reference,
original status and creation time. They do not copy message bodies or response
snapshots. No receipt expiry is configured: pruning without a defined retry
horizon could allow a delayed retry to duplicate a write. Retention policy and
legal erasure remain separate unresolved requirements.

## Evidence and limits

Eight local behavioral tests cover duplicate creation, actor scoping, conflict,
private replies after closure, staff notification/audit deduplication, revoked
roles, route retries preserving newer state, transaction rollback, invalid input
and legacy clients. The PostgreSQL concurrency test sends the same creation twice
in parallel and expects one ticket/message/receipt; it is authored but skips in
the SQLite environment. PostgreSQL validation remains required before production.

Queue pagination and bounded message history are now delivered in the next
checkpoint; see [support history](SUPPORT_HISTORY.md). Real-time transport,
attachment handling, presence, external notifications and production abuse
limits remain future support work. Retry keys are not an abuse-control mechanism.
