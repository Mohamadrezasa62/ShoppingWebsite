# Release 0.2.0 — AI marketplace assistants

Status: approved for implementation; acceptance is tracked per milestone.
Baseline: the existing Django, Next.js, PostgreSQL, Redis, and Celery stack.
This release adds assistant capabilities without treating unfinished checkout,
payments, fulfillment, or launch work as complete.

## Competitor evidence and product choices

- Digikala Dia: product finding, shopping consultation, and question answering
  in Persian. Source: https://t.me/s/digikalaofficialaccount/13943
- Amazon Alexa for Shopping (formerly Rufus): conversational product research,
  comparison, preferences, price history, and reviewed cart actions. Source:
  https://www.aboutamazon.com/news/retail/amazon-rufus-ai-assistant-personalized-shopping-features
- Walmart Sparky: product comparison, review synthesis, occasion planning, and
  shopping lists. Source:
  https://corporate.walmart.com/news/2025/06/06/walmart-the-future-of-shopping-is-agentic-meet-sparky
- Shopify Sidekick: merchant analytics, content drafts, and tasks presented for
  review before application. Source:
  https://help.shopify.com/en/manual/ai-powered-tools/sidekick

## AI-1 — Persian buyer shopping guide

**Deliver:** An RTL assistant on product and browsing pages; natural-language
shopping needs and budget constraints; grounded recommendations from published,
in-stock offers; specification questions and up to three-product comparisons;
approved-review summaries with source links; explicit uncertainty when the
catalog lacks information. Keep prices in toman and show live offer data.

**Acceptance:** Tests prove out-of-stock or hidden offers are excluded, budget
limits are honored, recommendations link to actual products, and unsupported
facts are not invented. A buyer can complete a guided search on desktop and
mobile. LLM service outage has a usable catalog-search fallback.

## AI-2 — Buyer shopping actions and account help

**Deliver:** Suggested cart changes with explicit confirmation, current price
and delivery explanations, scoped order lookup, and optional preference memory
with view, correction, and deletion controls. No automatic charge, purchase,
cancellation, financing decision, or refund. Use existing commerce services.

**Acceptance:** Cross-account requests are denied; a cart change happens only
after buyer confirmation; price and stock are rechecked by the cart service;
memory is opt-in and removable. Actions and consent are auditable.

## AI-3 — Seller assistant

**Deliver:** Seller-scoped product-description drafts, offer-quality guidance,
own-store sales and stock explanations, and restock suggestions. Drafts are
editable and require seller confirmation before saving.

**Acceptance:** Tests prevent data leakage across sellers and prove drafts do
not publish or alter offers automatically. Sales claims cite the underlying
store records and date range.

## AI-4 — Administrator assistant

**Deliver:** Staff-scoped support-case summaries, catalog-quality flags, and
questions over permitted operational reports. All proposed changes use the
existing staff workflows, with role checks, confirmation, and audit records.

**Acceptance:** Restricted staff cannot see finance, provider secrets, or
another role's records. Summaries link to source cases. No privileged action
occurs without a permitted staff user approving it.

## Shared delivery requirements

- One server-side AI gateway with configurable provider and model; no keys in
  the browser or repository. Catalog and private data tools have allowlisted
  inputs, role checks, bounded outputs, rate limits, and timeouts.
- Persian and RTL quality checks; accessible keyboard and mobile use.
- Distinguish factual catalog values from generated explanations. Log response
  quality, latency, cost, and errors without exposing sensitive chat content.
- Treat catalog descriptions, reviews, and user prompts as untrusted data.
- Roll out behind feature flags, collect feedback, and compare task completion
  against ordinary search and manual workflows.

## Release gate

Each AI milestone uses its own branch and commit. Tests and build checks must
pass before push. The release remains unaccepted until all four milestone
acceptance checks and privacy, security, accessibility, and pilot checks pass.
The existing marketplace launch gates in `docs/launch/READINESS.md` remain open.
