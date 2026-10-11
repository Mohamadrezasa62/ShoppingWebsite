# Zarinpal payment candidate

This checkpoint implements creation and server verification, not acceptance for
real-money launch. Official contract checked 2026-10-11:
https://www.zarinpal.com/docs/paymentGateway/connectToGateway

The v4 request/verify host is `payment.zarinpal.com`. Request amounts explicitly
use IRR: immutable order Toman total multiplied by ten. Verification sends the
same Rial amount and stored authority. Codes 100 and 101 with a positive integer
receipt are accepted; browser query status never constitutes cash verification.
No card PAN/hash, merchant response body or customer contact is stored/logged.

## Configuration and routes

Apply payments migration 0004. Default `ZARINPAL_ENABLED=0` remains off. To
configure a reviewed test deployment set the private `ZARINPAL_MERCHANT_ID` UUID,
actual HTTPS SITE_URL and `ZARINPAL_ENABLED=1`. This adapter contacts the **live**
host, not the provider sandbox. Do not enable it for casual/demo testing. Unit
fixtures mock the transport and no remote financial request was made here.

Existing `POST /api/v1/payments/initiate/` accepts provider `zarinpal`, order_id
and idempotency_key. It requires ownership/active account and CSRF. Only the
server's current payable order total is accepted. At most five attempts per
order; any unreconciled/active attempt blocks another. The returned redirect URL
uses the exact fixed HTTPS host/StartPay path. The UI permits only that URL or
its existing development sandbox path and uses the appropriate payment label.

Callback is `GET /api/v1/payments/zarinpal/callback/{random-64-hex-token}/` with
single Authority and Status parameters. The authority must match the stored
value. Status=OK triggers server verification; NOK merely returns to owned order
history and never rejects/captures/releases an order. Callback response exposes
no order/customer/payment details, and sets no-referrer/no-store. Each known
attempt gets 20 verification requests per ten-minute fixed window in shared
cache; cache outage fails closed. Treat callback tokens as secrets; redact URLs
in any external edge/APM logging. Application route logs do not include tokens.

Owned authenticated `POST /api/v1/payments/{id}/verify/` with `{}` lets an
integration retry verification, with the same budget and CSRF. Customer recovery and an audited finance re-verification queue are now
implemented; see [payment recovery](R5_PAYMENT_RECOVERY.md). Provider/bank
reconciliation and missing-authority recovery are still outstanding.
Verification of known attempts works when new initiations are disabled while the original merchant credential
is retained. Payment rows store only its SHA-256 fingerprint. A changed merchant
credential blocks old attempts until the original is restored from the private
secret store; do not discard old credentials before reconciling open attempts.

## Transaction/failure semantics

Creation first commits a durable `created` attempt, then contacts the provider
outside a database lock. Same-key creation retries reuse a stored successful
redirect; in-flight/unknown results never send a second creation request. A
negative authenticated provider response marks rejected. Timeout/malformed
response marks `initiation_unknown`. A process crash may leave `created`.
Both block new attempts, because provider acceptance may have occurred.
Operational recovery for an unknown authority is not automated: compare provider
records under a documented reconciliation policy. Do not simply delete the row
or change it to rejected to bypass this guard. No provider idempotency support
or exactly-once external creation is claimed.

Verification locks parent order then attempt and performs the provider call
under these locks (socket timeout 10 seconds; not a total deadline). Capture
uses existing atomic cash/stock services. Repeated verification returns existing
capture without another provider call. If the database transaction fails after
provider verification, a later provider 101 response recovers local capture.
Paid-after-expiry/cancellation or amount/stock incompatibility records real cash
as review_required without fulfillment; finance must reconcile/refund it.
Reference conflicts do not create a second ledger entry. HTTP transport rejects
redirects, oversized responses and malformed data; no automatic retry occurs.

## Remaining launch gates

Thirteen new SQLite behavior/transport tests pass; two PostgreSQL races are authored
but skipped locally. No merchant account/real gateway or HTTPS callback test was
performed. Execute contention, operator reconciliation, provider sandbox/live
pilot and full browser flows on staging before enabling commercial traffic.
Provider refund, unresolved-authority recovery, periodic reconciliation, bank
settlement/payout integration and monitoring are not implemented by this adapter.
Live enablement is not sufficient for `deployment_preflight --launch` acceptance.
