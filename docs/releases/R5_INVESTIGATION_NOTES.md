# Private payment investigation history

Development checkpoint 26. This is an operational record of staff observations;
it does not establish bank/provider reconciliation or change payment/order state.

## Contract

Finance operators/system administrators can read
`GET /api/v1/payments/finance/{attempt_id}/notes/` and write
`POST /api/v1/payments/finance/{attempt_id}/notes/append/`.
Customer, seller and support-only roles cannot access these routes. Notes are not
included in customer payment history or CSV export. Read output contains only
note ID, attempt ID, staff ID, entered body and creation time; it does not include
staff contact, callback token, merchant fingerprint or redirect URL.

POST accepts exactly `reason` (trimmed text 3–500 characters, no NUL) and
`request_key` (canonical nonzero hyphenated UUID). CSRF is required. The actor row
is locked and active/staff/finance authority is rechecked before creation or
replay. The actor/request-key unique constraint and lock serialize retries.
Same key/attempt/trimmed text returns the prior note with replayed=true and no
new audit; changed text or attempt conflicts (409). Other actors have independent
key namespaces. Failure consumes neither note nor key. A successful new note
returns 201, replay 200.

Creating the note and payment_investigation_noted audit is one transaction.
Audit reason is the staff-entered note, metadata contains only note ID. Required
audit failure rolls back the note. Staff must not enter OTPs, credentials, card
information or private customer details; arbitrary entered text is not an
automatically redacted secret store. Audit reasons also need approved retention.
There is no update/delete endpoint; model save rejects updates to existing notes.
Corrections are appended. Privileged direct SQL/ORM bypass is outside API claims.

GET accepts only one `before` positive decimal cursor. Descending note IDs,
20 returned rows and one lookahead row bound each page; an attempt/ID index
supports history. Unknown/repeated filters and invalid cursors return 400,
missing attempt 404. This timeline contains staff notes, not provider events,
verified evidence, status transitions or automatic investigation resolution.

## UI and deployment

Finance payment cards open the timeline on demand, refresh, navigate older/newer
pages and append escaped plain text. Request keys are retained for unchanged
failed submissions while the component remains mounted, not across refresh,
filter changes, page unmount or offline sessions. Stale history responses are
ignored. Success resets history to its newest page. Display timestamps are
localized in the browser; stored timestamps remain aware datetimes.

Apply payments migration 0005 using the existing release job with writes paused
for an upgrade. It creates a note table/index/constraint without rewriting cash,
orders or inventory. No retroactive notes or fabricated investigations are seeded.
Private payment records remain in the finance queue after a note is added.

## Verification and gates

Ten local behavioral tests cover role/CSRF boundaries, strict input, retry
conflicts and actor scope, audit rollback, history isolation/paging/bounded
queries, inactive/role-revoked actors, customer-field exclusion, append-only save
and unchanged financial/inventory state. One PostgreSQL concurrent same-key
retry test is authored and skipped locally; it is not a PostgreSQL pass.
Latest full tests/build are recorded in IMPLEMENTATION_STATUS.md. Browser UI,
PostgreSQL deployment and actual provider investigations remain unverified.

Unknown-authority payment recovery, automated matching, real refunds/payouts,
provider/bank acceptance and live pilot remain open. Notes cannot supply authority,
amount, receipt or paid overrides; production launch gates stay closed.
