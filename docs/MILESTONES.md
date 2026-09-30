# Delivery milestones

## Product assumptions

- Market: Iran; Persian-first, right-to-left, mobile-friendly interface; toman display and explicit currency-unit handling in payment integrations.
- Business: multi-seller marketplace. A shared product may have multiple seller offers, each with its own price, stock, warranty, and fulfillment method.
- Channels: responsive web storefront, seller portal, and administrator portal. Native mobile apps are outside the first release.
- Platform: Docker Compose development stack with a Django API, separately containerized frontend, PostgreSQL, Redis, and background worker. Production may use an orchestrator while keeping the same service boundaries.
- Launch: milestones 1–10 form the first public release. Milestone 11 is later expansion.
- Provider names are integration targets, not claims of an existing agreement or unrestricted API access.

## 1. Product and design specification

**Deliver:** Personas and buyer, seller, support, and administrator journeys; page inventory and navigation; responsive RTL wireframes; design tokens; domain glossary; product/variant/offer/inventory/order state models; provider decision record; prioritized requirements and analytics events.

**Acceptance:** The specification covers one product offered by several sellers, a multi-seller cart, stock reservation, split fulfillment, cancellation, and refund. Every core journey has a clear actor, trigger, outcome, and failure path. Open commercial decisions are recorded with an owner rather than guessed.

**Depends on:** None. This milestone defines the contracts for the rest.

## 2. Platform foundation

**Deliver:** Dockerized frontend and Django API; separate PostgreSQL, Redis and background-worker services; migrations and seed data; phone-based customer sign-in and staff sign-in; role-based access; file/media storage abstraction; development and test environments; CI checks; logging, error tracking, and health checks.

**Acceptance:** Buyer, seller, and admin accounts can access only their permitted areas in a deployed test environment. A fresh checkout can be installed, migrated, seeded, tested, and started from documented commands.

**Depends on:** 1.

## 3. Full administrator panel

**Deliver:** Staff accounts, roles and permissions, two-factor authentication for privileged roles, audit log; catalog taxonomy and moderation; seller application review, suspension and commissions; order intervention; return/refund casework; storefront content and campaigns; shipping rules; provider configuration; finance and settlement views; support queues, moderation, dashboards, exports, and operational alerts.

**Acceptance:** Authorized staff can perform the catalog, seller, order, finance, and support tasks through the panel without direct database edits. Sensitive changes identify actor, timestamp, before/after values, and reason. Restricted staff cannot access finance or provider secrets. Destructive actions require appropriate confirmation and can be traced.

**Depends on:** 2. Modules can be delivered incrementally alongside later milestones, but all listed workflows must pass before milestone 3 is accepted.

## 4. Catalog and discovery

**Deliver:** Categories, brands, products, variants, attributes, media, seller offers; search with suggestions, filters and sort; category and product pages; availability and delivery estimates; SEO metadata.

**Acceptance:** A buyer can find a product, filter results, select a variant, compare seller offers, and see the correct price, warranty, stock, and delivery promise on desktop and mobile.

**Depends on:** 1–3 for data and admin workflows.

## 5. Seller portal

**Deliver:** Seller registration and verification workflow; store profile; product matching and proposed products; offer price and stock editing; bulk import; order queue; shipping workflow; sales, fees, and settlement reports; support cases.

**Acceptance:** An approved seller can publish an offer, maintain its stock and price, process an order, and inspect the resulting fee and settlement entries without staff or developer intervention. An unapproved seller cannot publish.

**Depends on:** 2–4.

## 6. Cart and checkout foundation

**Deliver:** Persistent cart; address book; delivery grouping and rates; delivery method and slot selection; discount and gift-card rules; tax/fee calculation; immutable order price snapshots; stock reservation; order creation and expiration.

**Acceptance:** A multi-seller cart produces accurate item, shipping, discount, and total amounts. Concurrent checkouts cannot oversell stock. An expired or abandoned checkout releases reservations. Order totals remain stable after offer prices change.

**Depends on:** 4–5.

## 7. Payments and financing

**Deliver:** Provider-neutral payment state machine and ledger; one conventional online card gateway; adapters targeted for Tara, SnappPay, and DigiPay; payment selection and eligibility display; redirects/callbacks; server-side verification; idempotency and retries; reconciliation; admin transaction view; supported full/partial refunds and settlement reporting. Document an adapter contract for future providers.

**Acceptance:** Test orders cover success, rejection, timeout, duplicate callback, callback before browser return, amount mismatch, and refund. Orders are marked paid only after trusted server-side verification. Each named provider is enabled in production only after merchant onboarding, documentation, credentials, and sandbox/production certification are available; unavailable providers remain clearly tracked as integration blockers rather than represented as working payment methods.

**Depends on:** 6 and provider agreements. Exact eligibility, split payment, refund, settlement, and currency-unit rules follow each provider's signed contract.

## 8. Fulfillment and customer service

**Deliver:** Seller-fulfilled and platform-fulfilled shipment states; tracking; buyer notifications; cancellation; return authorization and evidence; refund orchestration; support case tools; delivery and return reporting.

**Acceptance:** Test orders can move from payment to delivery, cancellation, or return/refund. Buyers, sellers, and staff see consistent states, and refunds cannot exceed captured payments.

**Depends on:** 5–7.

## 9. Trust and merchandising

**Deliver:** Verified-purchase reviews and ratings, product questions, moderation, wishlists, product comparison, coupons and campaigns, homepage sections, merchandising rules, basic recommendations.

**Acceptance:** A buyer can use comparison and trust signals to choose an offer. Staff can schedule and run a campaign, and promotion totals match checkout calculations.

**Depends on:** 3–8.

## 10. Launch readiness

**Deliver:** Security review, accessibility and RTL QA, performance/load testing, mobile/browser testing, observability, backup and restore rehearsal, analytics dashboards, support procedures, seller pilot, launch checklist.

**Acceptance:** Realistic pilot purchases and refunds pass end to end; critical defects are closed; operational owners can diagnose incidents and restore service; legal and payment-provider launch requirements are satisfied.

**Depends on:** 1–9.

## 11. Expansion

**Candidates:** Personalized recommendations, loyalty points, paid membership, seller ads, wallet/credit enhancements, grocery and rapid delivery, advanced logistics, native apps.

**Acceptance:** Each selected feature gets its own measurable goal and acceptance criteria based on launch data before implementation.

**Depends on:** 10 and observed demand.

## Delivery rules

1. Keep implementation for each milestone on a dedicated branch and review it before merging to `main`.
2. Commit code, migrations, tests that protect important behavior, documentation, and required configuration together. Never commit credentials.
3. Run relevant automated and manual checks, then record evidence against the acceptance criteria.
4. A milestone ends only when its accepted changes are merged, committed, and pushed. Tag the accepted `main` commit `milestone-N`.
5. Record external dependencies and unresolved decisions explicitly; do not mark unavailable provider integrations complete.
