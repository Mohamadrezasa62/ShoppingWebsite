# Baseline and execution checkpoint

Date: 2026-10-11. Source inspected: `8da3446beccd00b46644973792cf786e05a72364`.

## Baseline actually executed

- Python 3.12.14; Node 24.19.0; npm clean install completed.
- Original Django suite: 43 tests passed with `TEST_SQLITE=1 DJANGO_DEBUG=1`.
- Original model migration check: no changes detected.
- Original frontend TypeScript and production build: passed.
- Docker is not installed; Compose, PostgreSQL and Redis were not started locally.
- Existing CI already had PostgreSQL, Redis, frontend and Compose jobs. This was
  missed in the initial file inventory; the roadmap's suggestion to add CI
  should be read as verifying and completing it, not creating it from zero.
- Existing Compose smoke check used ports 8000/3000 while Compose exposes
  5068/5067. Those checks are corrected in this development branch.
- Frontend Docker build now sets API_INTERNAL_URL before `next build`, so its
  compiled rewrites target `api:8000` rather than container-local localhost.

## Execution contract

Retain the modular Django application, Next.js frontend, session/CSRF web
authentication and integer-toman amounts. Retain shared Product/Variant and
seller-specific Offer. Retain current API namespaces; add endpoints within
them rather than silently breaking existing clients. Use command endpoints
for delivery transitions; sellers cannot self-confirm customer receipt.

OrderDelivery remains the fulfillment grouping until the finance/seller-order
contract is resolved. No separate SellerOrder is claimed complete. Current
return model is not yet safe for quantity-level partial returns. Inventory
locations, tax rules, promotion allocation and settlements remain open.

## Business decisions and external blockers

| Decision or access | Required owner | Blocked acceptance |
|---|---|---|
| First gateway agreement, docs, sandbox credentials and callback rules | Business + Payments | R5 / real checkout |
| SMS provider credentials and delivery contract | Business + Platform | R1 production authentication |
| Tax/invoice, merchant of record, commission and payout policy | Finance + Product | R4 / R7 |
| Seller KYC rules, documents and bank verification | Marketplace operations | R3 |
| Launch categories, return/cancellation windows and carrier contract | Product + Operations | R0 / R6 |
| Deployment target, domain, TLS proxy and durable storage | Platform owner | R10 |

These are tracked requirements, not fabricated integrations. Local development
can continue behind disabled provider methods. R0 is not fully accepted until
the decisions and PostgreSQL/Compose evidence are available.
