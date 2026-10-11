# Implementation status

Updated 2026-10-11. Development branch: `development/milestone-foundation`.

## Delivered in this branch

- Repeatable development-only `seed_demo` with one variant and two sellers;
  no passwords, staff accounts or captured payments are generated.
- Bounded request correlation IDs, API cache protection and optional structured
  request logs without bodies, query strings, phone numbers or credentials.
- Configurable TLS redirect/HSTS/proxy trust and documented session lifetime.
- Profile update with explicit field allowlist, CSRF and customer account UI.
- Address PATCH with ownership and validation; malformed quote IDs return 400.
- Checkout idempotency rejects changed address payloads for new orders.
- Idempotent unpaid-order cancellation; reservations release once and never
  use this path for paid orders.
- Customer order history/detail UI with fulfillment status and tracking.
- Role-restricted, audited product creation/editing/publication and variant
  creation, with paginated product management UI.
- Seller paid-order queue and packing/shipping API/UI; seller isolation and
  tracking validation; seller cannot self-confirm delivery.
- Role-restricted admin order list/detail and audited delivery transitions/UI.
- Existing CI retained and extended with repeatable demo seed and PostgreSQL
  race tests. Compose smoke ports and frontend Docker proxy build fixed.

## Second development checkpoint

- Development-only sandbox payment initiation and capture UI, explicitly disabled
  in production; no real gateway or money transfer is claimed.
- Quantity-level returns, inspection-controlled restocking, sandbox refunds,
  exact discount allocation and seller payable reversals.
- Commission snapshots, seller payable subledger, settlement snapshots,
  separate creator/approver control and simulated payouts. This is not a
  certified accounting general ledger.
- Fixed/percentage coupons with limits, checkout snapshots and cart/admin UI.
- Wishlist, verified-purchase reviews, moderation, customer support tickets,
  private staff notes, in-app notifications and published content pages.
- All-device session revocation, seller CSV import/export with stock validation,
  private seller finance reports and role-restricted marketplace sales reports.
- Owned order statement downloads, server-rendered product/content metadata,
  canonical URLs, sitemap and robots configuration.

For local payment simulation set `DJANGO_DEBUG=1` and
`ENABLE_SANDBOX_PAYMENTS=1`. Production refuses the sandbox flag. Configure
`SITE_URL` before the frontend Docker build for canonical links.

## Third development checkpoint

- Product questions can be submitted by authenticated customers without a
  purchase requirement. Each customer has at most three pending questions per
  product; a user-row lock serializes that limit on PostgreSQL.
- Public responses contain only published questions with answers, exclude user
  identity, and respect product/category/brand visibility.
- Catalog/support staff can answer, publish or reject questions with a required
  audit reason. Customer and admin interfaces are included.
- Tests cover publication, role restrictions, CSRF, malformed input, pending
  limits, hidden brands and public identity minimization.
- Production webpack build passed directly in the current runtime without the
  earlier memory-probe fallback. PostgreSQL concurrency and browser E2E remain
  unverified locally.

## Fourth development checkpoint

- Transactional internal outbox integrated with order creation, capture,
  cancellation, expiration, fulfillment and returns. Retry/savepoint isolation,
  dead-letter state, audited replay and administrator UI are implemented.
- One-shot private product stock/price subscriptions with explicit customer
  consent, keyset batch scanning and generation-based unsubscribe suppression.
- Customer-only downloadable activity export excludes staff notes and secrets.
- OTP consumption now uses an atomic nonce marker to prevent stale concurrent
  reads from authorizing the same code twice.
- Seller performance API/UI and role-restricted admin seller report, with item
  totals clearly separated from cash, shipping and inferred conversion.
- Five authored PostgreSQL contention tests; SQLite execution skips them.
- Operational instructions: [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md).

## Fifth development checkpoint

- Private seller product proposals and audited staff approval/rejection, with
  approval creating a catalog draft and variant atomically. Duplicate SKU
  conflicts roll back the entire operation; reviewed proposals cannot repeat.
- Image upload/processing and moderation UI: JPEG/PNG/WebP input, bounded size
  and pixels, normalized metadata-free PNG, private previews and explicit
  publication. Unknown file formats and customer uploads are rejected.
- Scheduled product collections, staff management, public server-rendered pages,
  canonical URLs and sitemap inclusion. Unavailable offers stay out of cards.
- Same-category related products and updated customer homepage links.
- Mobile browser E2E flow and PostgreSQL/Redis CI job authored. Chromium download
  failed locally (truncated archive), so no browser pass is claimed.

## Sixth development checkpoint

- Audited brand and category-facet creation/update and management interfaces.
- Facet keys reject ORM lookup operators and numeric indices; public filtering
  also rejects invalid legacy facet keys instead of generating unsafe queries.
- Audited province/fulfillment shipping fee and delivery-window management,
  restricted to marketplace/system roles; validation rejects reversed windows.
- Full catalog product metadata editing, category/brand selection, specification
  editing, and clear product IDs for media and merchandising workflows.
- Persian global loading and retry boundaries follow the installed Next API.

## Seventh development checkpoint

- Customer requests can cancel one paid seller delivery before shipping, without
  stopping another seller's delivery. Pending/approved requests hold fulfillment.
- Marketplace review and finance refund actions have separate role checks and
  audit reasons. Rejection releases the hold; one case is allowed per delivery.
- Development-only sandbox refunds restore inventory exactly once, refund net
  item prices plus that delivery's shipping, and preserve the captured payment
  state on the parent order. Refunds are separate immutable ledger entries.
- Customer/order, seller fulfillment and administration interfaces include this
  workflow. Seller reports separate cancelled units and refunded shipping.
- Tests cover repeat requests/refunds, ownership, review permissions, shipping
  holds, rollback, production safeguards and partial-order financial totals.

## Eighth development checkpoint: privacy, recovery and measured catalog

- Customer account-closure requests, withdrawal and system-role review are
  available in account/admin interfaces. Completion disables access and product
  alerts, revokes sessions and retains identity/order/financial records. This is
  deactivation, not legal erasure. Staff/seller offboarding remains separate.
- Pending payments, open deliveries, returns and cancellations prevent account
  closure. Checkout and seller onboarding serialize on the account row and
  recheck active status before creating new commercial work.
- Catalog cards avoid loading full descriptions/specifications; related products
  apply the eight-item limit before loading rows and image metadata.
- A read-only catalog profiler records local timing/query-count/response-size
  evidence. A synthetic 1,000-product/2,000-offer SQLite run is documented in
  [R12/CATALOG_PROFILE.md](R12/CATALOG_PROFILE.md); it is not a production load test.
- A read-only commerce consistency command detects reservation/snapshot/capture/
  refund mismatches, outputs bounded reference-only defects and never repairs
  financial data. PostgreSQL standalone execution requests a repeatable-read,
  read-only transaction. SQLite behavior is verified; PostgreSQL remains open.

## Ninth development checkpoint: followed catalog and closure races

- Customers follow visible brands/approved sellers from product pages, manage
  up to 100 private follows and view a bounded feed of available products.
  Duplicate follows are idempotent; other customers cannot read/remove them.
- Feed visibility follows current catalog/seller/stock rules and avoids duplicate
  product cards. Following does not imply consent to marketing messages or
  activate an external channel; owner exports include follow targets.
- Return requests also serialize on the account row before order locks, preventing
  account completion from racing with a new unresolved return. A PostgreSQL-only
  contention test is authored; its SQLite skip is not execution evidence.
- Local non-development Django configuration review reports two open TLS
  settings, documented in [R10/CONFIG_REVIEW.md](R10/CONFIG_REVIEW.md).

## Tenth development checkpoint: disputes, consent and catalog jobs

- Owned paid-delivery disputes, private seller responses and audited operator
  escalation/resolution are available in customer, seller and admin interfaces.
  Open cases block account closure and unpaid seller settlement/payout. Resolution
  does not issue a refund or reverse a payout that already completed.
- Marketing in-app consent defaults to off, is customer-controlled and separate
  from transactional notifications. Scheduled campaigns use capped, keyset-batched
  audiences and recheck consent generation at delivery; cancellation, expiry and
  withdrawal suppress queued messages. External transports remain unconnected.
- Coupons support a total discount budget, reserved by pending/paid order
  snapshots under checkout locking. Unpaid cancellation releases the budget;
  paid refunds conservatively retain consumed budget.
- Catalog CSV jobs validate bounded input, create drafts atomically in the outbox,
  recheck operator authority, reject duplicate identifiers and expose row-level
  failure metadata. Audited retry uses a new generation; successful jobs discard
  source rows. Staff can download bounded, spreadsheet-safe catalog CSV pages.
- Tests cover ownership, roles, CSRF, private-note exclusion, campaign suppression,
  retry/savepoint rollback, budget release, whole-file rollback and export limits.
  Three additional PostgreSQL race tests are authored, not locally executed.

## Eleventh development checkpoint: purchase trust and operational review

- Customers rate one paid, delivered seller delivery. Identical repeat submissions
  return the same review; changed submissions conflict. Seller members cannot
  rate their own store. Staff moderation is audited; public seller pages show
  published reviews and aggregate ratings without buyer identity or contacts.
- Public comparison supports two to four currently available products, preserving
  selection order and comparing bounded specifications with current starting
  prices. Missing/hidden products fail the whole comparison rather than leaking
  partial data. The UI supports search, selection and shareable URLs.
- Owners attach at most three images per product review, using bounded, normalized
  metadata-free PNG processing and idempotent upload keys. Text and image approval
  are independent; public access requires both approvals and visible catalog.
  Owners withdraw images permanently from display, with audited moderation and
  private previews. Stored bytes still require a retention/erasure policy.
- Internal order risk cases support audited human review and optional fulfillment
  holds. Holds serialize with packing/shipping; dispatched delivery confirmation,
  payment recording and returns remain possible. Clearing a case explicitly
  releases its hold, even with a confirmed concern; no automatic refund, fraud
  scoring, account block or cancellation is claimed.
- Support tickets support priority, assignment to eligible active staff and manager
  escalation. Escalated tickets cannot close until a manager clears escalation;
  replies preserve assigned ownership. Private routing data stays out of customer
  responses and exports. A PostgreSQL risk/shipping contention test is authored.
- Detailed scope and API evidence: [R8/TRUST_REVIEW.md](R8/TRUST_REVIEW.md).

## Twelfth development checkpoint: warehouse inventory

- Seller-owned warehouses maintain physical stock, reservations, versions and
  movement history. Checkout allocates available units across locations; capture
  consumes allocations, while unpaid cancellation/expiry releases them. Returns
  and paid cancellation restore the original logical allocation exactly once.
- Seller panels support warehouse management, version-checked adjustments,
  transfers of unreserved units and history. Atomic stock CSV imports reject
  stale versions and roll back the entire file on any invalid row; exports are
  bounded and spreadsheet-safe. Existing aggregate CSV cannot overwrite changed
  multi-location totals. Marketplace administrators have a private read-only view.
- Low-stock events generate deduplicated in-app owner notifications, suppressing
  replenished stock. The read-only consistency checker compares warehouse caches,
  reservations, movement history and restocks without attempting repairs.
- A migration rehearsal converted 2,000 legacy offers on a disposable synthetic
  SQLite copy with no consistency issues. PostgreSQL contention tests are authored
  but unexecuted. Details: [R3/WAREHOUSE_INVENTORY.md](R3/WAREHOUSE_INVENTORY.md).

## Thirteenth development checkpoint: approval, bulk editing and browsing history

- Ready checkout estimates issue a signed ten-minute approval token containing
  only account/address references and a snapshot digest. The storefront submits
  it; changed prices, quantities, warranty, address, shipping promise or discount
  require a new customer confirmation. Failure preserves the cart and stock.
  Original accepted retries remain idempotent after token expiry. Existing API
  callers may omit the token during migration and retain recalculation semantics.
- Catalog CSV jobs now support revision-checked content updates of existing
  products, with bounded exports, deterministic product locks, whole-file
  rollback and before/after audits. They preserve identifiers, taxonomy,
  publication, variants, offers and historical order snapshots. Worker processing
  rechecks authority; source rows are removed after success.
- Customers opt into private recently viewed products, disabled by default.
  Records deduplicate and cap at fifty products; reads/exports exclude records
  older than thirty days. Clearing keeps consent; disabling or completed account
  deactivation removes history. Hourly bounded cleanup is configured for Celery.
- Three additional PostgreSQL race tests are authored but unexecuted locally.
  Scope: [R4/CHECKOUT_APPROVAL.md](R4/CHECKOUT_APPROVAL.md),
  [R2/BULK_UPDATES.md](R2/BULK_UPDATES.md), [R9/HISTORY.md](R9/HISTORY.md).

## Fourteenth development checkpoint: selectable shipping and delivery windows

- Marketplace/system staff configure up to twenty additional shipping methods
  per province/fulfillment rule, with explicit total fee, label and relative days.
  Each seller delivery can choose its own method; standard shipping remains the
  legacy default. Selection and pricing are bound to signed checkout approval.
- Optional future delivery windows have capacity per seller delivery group.
  Quote previews do not reserve capacity; checkout locks selected windows and
  counts pending/paid bookings. Multiple groups choosing one window each consume
  a capacity unit. Unpaid cancellation/expiration and cancelled paid deliveries
  stop consuming capacity without changing historical window snapshots.
- Customers, sellers and staff see chosen method/window snapshots. Price changes,
  inactive methods, foreign province choices and stale/full windows are rejected.
  Admin mutations recheck authority, require CSRF/reason and roll back on audit
  failure. Dates cannot move once any historical booking exists; reductions cannot
  undercut live reservations. The read-only checker detects capacity/snapshot drift.
- Ten local regression tests passed. Two more PostgreSQL capacity/deactivation
  race tests are authored but unexecuted. The frontend build passed. Scope and
  contracts: [R4/SHIPPING_CHOICES.md](R4/SHIPPING_CHOICES.md).

## Fifteenth development checkpoint

- Owner-only order statements now include recipient/address snapshots, grouped
  seller deliveries, methods/windows, tracking, variant/warranty details and
  reconciled original delivery totals. Live catalog/configuration edits do not
  rewrite the recorded terms.
- Autoescaped templates, restrictive sandbox CSP, no-referrer, nosniff and API
  no-store protection cover the private download. Five regression tests cover
  ownership, snapshot stability, hostile text, multi-seller coupon totals and
  chosen shipping terms; query count does not grow with seller count.
- This remains an order statement, not a tax invoice, payment certificate or
  refund-adjusted balance. Browser/print QA is not claimed. Contract and evidence:
  [R4/ORDER_STATEMENTS.md](R4/ORDER_STATEMENTS.md).

## Sixteenth development checkpoint

- Explicit category tax rules with no assumed rate, audited role-restricted
  configuration and admin UI; missing/inactive rules default to zero.
- Tax after allocated coupon discount is bound to signed quote approval and
  immutable order snapshots. Product/category locks serialize rule creation
  and edits with checkout. Totals, statement, account export and customer UI
  show the recorded tax.
- Unit returns and paid cancellations refund original tax; seller payables and
  commission exclude it. Seller/admin reports distinguish item/tax/shipping
  components. Consistency checks detect order and refund component corruption.
- Ten new SQLite tests passed; two new PostgreSQL race tests are authored but
  unexecuted. No legal rate, tax filing, liability ledger or certified invoice
  is claimed. Scope: [R4/TAX_CONFIGURATION.md](R4/TAX_CONFIGURATION.md).

## Seventeenth development checkpoint

- Existing content pages can be edited and privately previewed in the panel,
  with optimistic version checks, immutable revision snapshots, paginated page
  and revision lists, and audited restores into a new unpublished draft.
- Optional publication windows use the same time-bound visibility query for
  public list/detail and sitemap. Exact boundaries are tested; schedules do not
  depend on a worker. The API requires aware datetimes and PATCH version tokens.
- Eleven new behavior tests and one existing-page migration test passed; two
  PostgreSQL edit/restore races are authored but unexecuted. Retention, review
  gates and parallel live/draft versions remain outside this checkpoint.
  Contract: [R8/EDITORIAL_WORKFLOW.md](R8/EDITORIAL_WORKFLOW.md).

## Eighteenth development checkpoint

- Shared-cache fixed-window peer budgets protect OTP requests/verification and
  staff credential rotation, with Retry-After. Forwarded headers are ignored;
  cache failures fail closed. Phone quota/cooldown spans both OTP purposes.
- Login confirmation binds the validated nonce and rechecks account authority
  under its row lock. Delayed consumption and delivery failures do not delete
  replacement OTPs; failed consumption rolls back new account creation.
- Self-service staff password rotation requires current password and a dedicated
  purpose-bound OTP, validates strength, audits without secrets and revokes all
  sessions. It does not provide forgotten-password recovery or bypass SMS.
- Thirteen new SQLite tests passed. One PostgreSQL authority race and two Redis
  parallel tests are authored and unexecuted locally; CI now opts into the Redis
  tests. Scope: [R1/AUTHENTICATION_SECURITY.md](R1/AUTHENTICATION_SECURITY.md).

## Nineteenth development checkpoint

- Actor-scoped UUID retry receipts for customer ticket creation/replies and staff
  replies/routing; changed endpoint or payload returns 409.
- Successful retries return the current private ticket without repeating messages,
  notifications, status changes or audit events. Failed transactions consume no key.
- Actor row locks and post-lock active-account/support-role checks protect writes
  and replay; customer internal-note filtering remains enforced.
- Support UI retains retry keys for unchanged failed submissions during the mounted
  session. Legacy clients remain compatible; reload/offline durability is not claimed.
- Operations migration 0009, eight behavioral tests and one authored PostgreSQL
  concurrency test. See [support retry safety](SUPPORT_RETRY_SAFETY.md).

## Twentieth development checkpoint

- Owner-private and staff-authorized conversation endpoints with stable older-message
  cursors; 20-message windows in list, write and conversation representations.
- 25-ticket queue pages, strict status/priority/assignment/escalation filters, stable
  ordering ties, and sliced message prefetch using two domain queries per queue.
- Support UI queue navigation, manual refresh and older-message loading with
  deduplication and stale-response guards. Account exports retain complete history.
- Seven new behavioral tests; see [support history contract](SUPPORT_HISTORY.md).
  Queue pages are not frozen snapshots and live-chat transport remains outstanding.

## Twenty-first development checkpoint

- Standalone HTTPS deployment Compose topology with only edge ports public,
  isolated internal services, explicit release migrations/static collection,
  durable volumes and a single scheduler.
- Nonroot backend and multi-stage/nonroot standalone frontend runtime; private
  environment exclusion and correct runtime canonical origin/TLS-marked SSR reads.
- Configuration/service preflight checks PostgreSQL, shared Redis, origin/cookie/TLS
  settings, migrations, roles and writable shared storage. Launch mode remains
  blocked by missing real providers and acceptance evidence.
- Readiness executes a real database query; nine deployment/readiness tests.
- Local standalone runtime smoke passed HTTP redirect, TLS-marked readiness, SSR
  collections and runtime HTTPS sitemap origin on SQLite; no real certificate tested.
- Authored Docker/Caddy/DB/Redis/release/SSR CI smoke workflow, not executed here.
  See [deployment candidate](DEPLOYMENT.md) for staging, migration/rollback and gates.

## Twenty-second development checkpoint

- Kavenegar OTP verification-template adapter using fixed-host HTTPS POST,
  bounded response/socket timeout, redirect rejection, no blind retries and
  redacted errors; separate customer/staff template settings and preflight checks.
- Failed submission consumes only its nonce and preserves cooldown/budgets;
  provider acceptance is not represented as confirmed carrier delivery.
- Fixed private edge address and explicit trusted-proxy client-IP identity;
  forged headers from other peers cannot select throttle buckets. Client
  budgets behind Caddy are independent; NAT/CDN caveats remain documented.
- Eleven mocked transport/security tests. No real provider call or credentials
  used; see [production SMS candidate](R1/PRODUCTION_SMS.md).

## Twenty-third development checkpoint

- Default-off Zarinpal live-host creation/server verification using order snapshots
  and explicit Toman-to-Rial conversion; merchant/authority/callback snapshots.
- Durable creation records, same-key redirect replay, unresolved-request guards,
  bounded attempts and no automatic creation retry after ambiguity.
- Secret callback token, authority binding, shared verification budget, owner-only
  CSRF retry endpoint; browser success never directly captures money.
- Capture/stock transaction recovery on provider 101, late money routed to review,
  exact redirect allowlist and customer payment labels.
- Payments migration 0004, thirteen local tests and two authored PostgreSQL races;
  no external charge made. See [payment candidate](R5_ZARINPAL.md).

## Twenty-fourth development checkpoint

- Owner-private payment history/recovery in order details, resume of existing
  redirects and explicit server re-verification; captured and refunded ledger
  totals displayed separately from expected amounts.
- Cursor-paged finance queue and audited role/CSRF-restricted re-verification,
  actor rechecks and transactionally committed cash/stock/audit results.
- Unknown authority remains blocked for provider reconciliation; no manual
  amount/receipt/paid override. Shared verification budget remains enforced.
- Shared exact-host payment redirect helper and malicious-input boundary checks,
  included in authored frontend CI. Eleven new behavioral tests and one additional
  authored PostgreSQL race. See [payment recovery](R5_PAYMENT_RECOVERY.md).

## Twenty-fifth development checkpoint

- Role/CSRF-restricted finance CSV exports of 25-attempt cursor pages, using
  the same strict filters as the investigation queue and freshly queried cash sums.
- Expected Toman/IRR and recorded capture/refund are separate; known gateway
  authorities allow provider-record matching without customer/token/merchant data.
- Required audit reason, locked actor rechecks, audit-before-download and CSV
  formula protection; no financial/order/inventory status changes.
- Finance UI downloads a freshly queried current filter/cursor page; this is not
  a frozen full-bank reconciliation report. Six new regression tests.
- See [export contract](R5_RECONCILIATION_EXPORT.md); launch gates remain open.

## Twenty-sixth development checkpoint

- Finance-only private per-payment investigation notes with required audit,
  bounded 20-row history and a dedicated indexed append-only API.
- Actor-scoped UUID retry keys, changed-payload conflicts and post-lock authority
  rechecks prevent duplicate notes/audits on retries; notes never change cash,
  stock, order or unresolved payment status.
- On-demand finance UI history and retry-preserving note submission; customer
  payment history and finance CSV remain free of internal note text.
- Payments migration 0005, ten behavioral tests and one authored PostgreSQL
  same-key contention test. See [investigation contract](R5_INVESTIGATION_NOTES.md).

## Verification commands

Latest local result: 366 discovered tests, 336 passed and 30 integration tests skipped
(28 PostgreSQL-only concurrency tests and two Redis tests). Django checks passed and no pending model migration
changes were detected. Frontend TypeScript and production webpack build passed directly in the current runtime.
An earlier checkpoint required a scratch-only Node memory metrics fallback;
that helper is not shipped and was not used for the latest build.

```bash
cd backend
TEST_SQLITE=1 DJANGO_DEBUG=1 python manage.py test
TEST_SQLITE=1 DJANGO_DEBUG=1 python manage.py makemigrations --check --dry-run
cd ../frontend
npm run typecheck
npm run build
```

PostgreSQL concurrency tests intentionally skip under SQLite; Redis tests skip
without AUTH_REDIS_TEST_URL. A passing local
suite does not establish their result. CI has been authored but not executed
on GitHub during this session. Browser E2E, Compose smoke, real-provider sandbox,
load, restore and production pilot remain outstanding.

## Milestone acceptance

| Stage | State | Principal remaining work |
|---|---|---|
| R0 | Partial | Business decisions, wireframes/OpenAPI and PostgreSQL baseline |
| R1 | Partial | Credential rotation, abuse limits and Kavenegar adapter delivered; verified SMS delivery, forgotten-password recovery, staging/storage/alerts remain |
| R2 | Partial | Draft import/export and version-checked content updates delivered; storage/CDN deployment and media retention remain |
| R3 | Partial | Location inventory and stock CSV delivered; KYC documents, bank verification and production concurrency evidence remain |
| R4 | Partial | Signed approval, shipping choices/windows and configured category tax delivered; approved tax policy/certified invoicing, gift cards, guest flow and PostgreSQL race evidence remain |
| R5 | Blocked externally; core partial | Zarinpal initiation/callback adapter delivered; certification, reconciliation, unresolved initiation recovery and real refunds remain |
| R6 | Partial | Carrier sync, individual-unit paid cancellation, real refunds, external notifications, return policy sign-off |
| R7 | Partial | Real payout integration, reconciliation, accounting and policy approval |
| R8 | Existing services partial | Trust services and versioned/scheduled content delivered; editorial review gates, parallel drafts, redirects and retention remain |
| R9 | Partial | Consent, recent history, in-app campaigns and coupon budgets delivered; loyalty, external channels, A/B tests and funnel analytics remain |
| R10 | Not accepted | HTTPS deployment candidate, preflight and consistency checker delivered; production deployment, security/load/actual restore/E2E and live pilot remain |
| R11 | Partial | Export, deactivation and manual risk review delivered; chat, advanced payments, loyalty, legal erasure, localization and integrations remain |
| R12 | Partial foundation | Outbox and local catalog profiling delivered; representative PostgreSQL load, independent search, native apps and multi-region remain |

No milestone acceptance, merge to main or production publication is claimed.
Development checkpoints are committed on the development branch.
