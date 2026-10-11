# Finance reconciliation export candidate

Implemented after checkpoint 24; no external-provider reconciliation or live
payment/refund acceptance is claimed.

## Contract

`POST /api/v1/payments/finance/queue/export/` accepts only JSON `reason` (3–500
trimmed characters, no NUL), requires CSRF and finance_operator or
system_administrator. The actor is locked and active/staff/role eligibility is
rechecked inside the transaction. This is a sensitive audited read, not capture,
refund, manual approval or an initiation retry.

Query parameters are the same strict single-valued `status`, `provider`, `before`
as the finance queue. Default statuses are created, initiation_unknown,
redirected and review_required. Invalid/unknown/repeated filters return 400.
Descending primary-key cursors bound each export to 25 attempts, with a 26th row
used only to detect another page. Response headers X-Has-Next and X-Next-Before
allow API clients to advance. The UI downloads the current cursor/filter page,
which is freshly queried and may differ from a stale on-screen page. Exports are
not a frozen multi-page snapshot or whole-market balance report.

UTF-8 BOM CSV columns: attempt/order IDs, provider/status, expected Toman and IRR
(Toman × 10), captured/refunded Toman from separate ledger sums, gateway authority,
provider reference, unknown-initiation flag and creation/update timestamps.
Known gateway authority is included only in this finance export for matching
provider records. Callback token, merchant fingerprint, redirect URL, customer
identity/contact/address and card data are excluded. Expected amounts are not
bank-confirmed balances. Provider receipt is not proof of bank reconciliation.
Fields starting with formula markers after whitespace are apostrophe-prefixed;
CSV quoting handles embedded delimiters. Financial rows with missing authority
remain unresolved and are never fabricated or marked paid.

Successful export records payment_queue_exported with actor, reason, attempt IDs,
filters and cursor metadata. No receipt/authority is copied into audit metadata.
Audit failure returns no CSV. Repeated exports create new audit entries, without
changing money/stock/order state. Response is attachment CSV with no-store,
nosniff and no-referrer; middleware reinforces API no-store. Operators must treat
downloads as private financial data and apply approved storage/retention rules.

## Verification and remaining gates

Six regression tests cover roles, CSRF/filter/reason validation, private-field
exclusion and units, paging/formula injection, nonduplicated refund sums and
unresolved flags, audit failure and post-lock inactive-actor denial.
Frontend typecheck/build and full backend suite are recorded in
IMPLEMENTATION_STATUS.md. Browser download/Excel visual QA and PostgreSQL runtime
remain unexecuted locally. No migrations are needed.

This export assists manual investigation; bank/provider imports, automated
matching, signed evidence, unknown-authority recovery, real refunds/payouts,
operator acceptance and live pilot remain open. The launch gate stays closed.
