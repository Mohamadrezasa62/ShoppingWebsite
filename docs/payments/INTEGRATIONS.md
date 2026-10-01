# Payment integration status

Milestone 7 has a provider-neutral attempt record, immutable ledger entries, a
read-only admin transaction view, and a private verified-capture service. Every
buyer-facing payment method is disabled. No merchant gateway is connected and
no order can be paid through the public API yet.

## Adapter contract

An approved adapter must implement checkout creation, server-to-server capture
verification, refunds, and reconciliation. It must authenticate provider
responses and map the provider's currency unit explicitly to integer tomans.
Browser redirects and callback parameters are untrusted notifications; they
must never directly mark an order paid. A verified capture records the received
amount in the ledger. The order becomes paid only if its amount, reservation,
and payment window still match. A late or mismatched capture enters manual
review while remaining visible in the ledger.

The adapter also needs a stable provider reference and idempotent request key.
Provider credentials belong in secret configuration, never source control.
Capture, refund, and reconciliation must be tested in each provider's sandbox
before enabling its method in production.

## External blockers

For the conventional card gateway, Tara, SnappPay, and DigiPay, obtain merchant
approval, current signed integration documentation, sandbox credentials,
callback authentication rules, currency units, refund rules, and production
certification. Their APIs, eligibility rules, and settlement terms are not
assumed by the current code. The methods endpoint intentionally returns no
available methods until these items are verified.

## Remaining milestone 7 work

Implement certified adapters and checkout initiation, callback handling,
provider verification, rejection and timeout handling, reconciliation jobs,
partial and full refund orchestration, settlement reports, and an end-to-end
payment selection flow. Record sandbox evidence for each provider separately.
