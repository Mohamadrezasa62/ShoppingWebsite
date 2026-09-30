# Milestone 1 — product requirements draft

Status: in progress. This document defines the first public release, not a claim that these features exist yet.

## Product goal and boundaries

Enable customers in Iran to compare offers from independent sellers and complete a reliable purchase in Persian. The first release includes a responsive web storefront, seller portal, and full administrator panel. Native mobile apps, an in-house credit product, and an in-house delivery fleet are outside the first release.

The approved platform direction is a containerized Django backend with separately containerized frontend, PostgreSQL, Redis and background worker. See [the architecture decision](ARCHITECTURE.md).

Success measures for the pilot are completed paid orders, checkout conversion, on-time dispatch, refund completion time, search success, and seller activation. Numerical targets need a pilot baseline and business owner.

## Actors and permissions

| Actor | Primary tasks | Permission boundary |
| --- | --- | --- |
| Guest | Browse, search, compare, build a cart | Cannot place an order or post a review |
| Buyer | Manage account and addresses, pay, track, cancel, return, review | Can see only their own orders and personal data |
| Seller staff | Manage assigned store's offers, stock, fulfillment, reports | Cannot edit another seller's data or canonical catalog without approval |
| Catalog operator | Review categories, products, media, and attributes | Cannot alter financial settlement or payment credentials |
| Support agent | Resolve buyer and seller cases and permitted order issues | Cannot silently change payment records or issue unrestricted refunds |
| Finance operator | Reconcile payments, refunds, fees, and seller settlements | Cannot change catalog content or provider credentials |
| Marketplace manager | Approve sellers, set commissions and campaigns | Sensitive changes are audited and subject to policy |
| System administrator | Configure roles, integrations, and operational settings | Uses privileged authentication and audited actions |

## Core journeys

| Journey | Trigger and normal outcome | Required failure path |
| --- | --- | --- |
| Discover and compare | Guest searches or browses; filters variants and compares seller offers | No matches, stale offer, unavailable location |
| Seller enrollment | Applicant submits business details; staff approves and seller can publish offers | Missing evidence, rejection, suspension, appeal |
| Catalog contribution | Seller matches an existing product or proposes a new one; staff approves canonical content | Duplicate product, prohibited content, rejected media |
| Checkout | Buyer selects offers, address, shipping and payment; paid order is created | Price/stock change, delivery unavailable, payment timeout or rejection |
| Fulfillment | Seller or platform dispatches each shipment; buyer receives tracking and delivery status | Late dispatch, lost shipment, partial delivery |
| Cancellation | Buyer or staff requests cancellation before permitted cutoff; stock and payment are restored | Item already dispatched, partial cancellation, refund delay |
| Return and refund | Buyer files a return, staff decides policy, item is received, refund is issued | Ineligible product, disputed condition, partial refund failure |
| Seller settlement | Finance verifies captured payments, commissions, refunds and payable balance | Charge mismatch, negative balance, held settlement |
| Admin intervention | Authorized staff edits an operational setting or resolves a case | Unauthorized action, validation failure, audit/log failure |

## Functional requirements

### Storefront

- Persian RTL layout, accessible mobile and desktop navigation, product categories, promotions, and configurable homepage sections.
- Search suggestions, category-specific facets, sorting, out-of-stock rules, and useful zero-result states.
- Product detail page with gallery, variant selection, specifications, warranty, delivery estimate, seller offers, ratings, questions, and comparison.
- Buyer account with phone verification, addresses, wishlists, order history, tracking, cancellation, return requests, and notifications.
- Cart and checkout with per-seller/per-fulfillment shipment grouping, stable totals, coupons, gift cards, and eligible payment choices.

### Seller portal

- Seller application, business identity review, store profile and staff access.
- Match existing catalog items or propose new products; manage offers, prices, stock, warranties and fulfillment preferences.
- Receive and process order lines and shipments; inspect returns, fees, settlements and performance.
- Bulk import/export with validation and row-level error feedback.

### Administrator panel

- Role and permission management, privileged sign-in, audit trail and staff lifecycle.
- Catalog/category/brand/attribute management, product and media moderation, duplicate resolution.
- Seller onboarding, verification, suspension, store settings, category commission schedules, performance and disputes.
- Order inspection and authorized intervention, delivery rules, cancellations, returns and refunds.
- Homepage/content management, campaigns, discounts, gift cards and scheduled publishing.
- Payment-provider settings without exposing secrets in the UI; transaction search, reconciliation, seller balances, settlement batches and exports.
- Customer and seller support queues, review/question moderation, operational dashboards and alerts.

### Payments

- A payment attempt belongs to exactly one checkout/order and records provider, amount, currency unit, status, provider references and timestamps.
- Capture/paid status requires server-side verification. Browser redirects alone are never authoritative.
- Tara, SnappPay and DigiPay are target adapters. Availability to buyers depends on executed merchant agreements, credentials, provider eligibility, supported product categories, and certification.
- Refund and settlement behavior is provider-specific and must be represented explicitly; the system must not promise capabilities the selected provider lacks.

## Nonfunctional requirements

- Security: least-privilege authorization on the server; secret management; audit trails; rate limits on authentication and payments; input validation; secure callbacks and idempotency.
- Correctness: amounts use integer minor units with a documented toman/rial conversion boundary; no floating-point money arithmetic; inventory reservations prevent overselling; immutable order price snapshots.
- Reliability: retryable asynchronous work, observability, backups and a tested restore path; payment state reconciliation after interruption.
- Accessibility and localization: RTL direction, Persian copy, readable digits and dates, keyboard navigation, visible focus, screen-reader labels, and mobile layouts.
- Privacy: collect only needed personal data, restrict access by role, define retention and deletion policies before production.
- Performance: establish search, product-page and checkout latency targets with pilot traffic and measure them in the launch rehearsal.

## Page inventory

| Surface | Pages/views |
| --- | --- |
| Storefront | Home, category, search results, product detail, comparison, wishlist, cart, address/delivery/payment checkout, payment result, account, orders, order detail, return request, help |
| Seller | Application, dashboard, catalog match/proposal, offers, inventory, orders, shipment detail, returns, finances, settings, support |
| Admin | Dashboard, catalog moderation, taxonomy, sellers, users/staff/roles, orders, returns, payments, reconciliation, settlements, shipping, campaigns, content, moderation, support, audit log, settings |

## Required analytics events

Search submitted, zero results, product viewed, variant chosen, seller offer chosen, cart item added/removed, checkout started, address/delivery/payment selected, payment attempt started/verified/failed, order placed, shipment dispatched/delivered, cancellation requested, return requested/decided, refund completed, seller application submitted/approved, offer published, and admin action completed. Events must exclude payment credentials and unnecessary personal data.

## Open business decisions

| Decision | Recommended working assumption | Owner needed before |
| --- | --- | --- |
| Launch categories and prohibited goods | Start with a small set of standard physical goods | Catalog build and seller onboarding |
| Fulfillment model | Seller-fulfilled first; design for platform fulfillment | Shipping contract and checkout rules |
| Payment providers and card gateway | One card gateway plus Tara, SnappPay and DigiPay after contracts | Live checkout integration |
| Merchant of record and settlement policy | Marketplace operator collects, then settles seller balances | Finance model and legal review |
| Commission, return windows and dispute policy | Category-based rules, versioned per order | Admin finance and returns |
| SMS, media storage and shipping partners | Adapter interfaces until vendor selection | Production integrations |
| Tax, invoice and legal requirements | Confirm with qualified local advisers | Production launch |

These open decisions do not prevent domain modeling or noncommercial UI work. They do prevent declaring the corresponding live workflows complete.
