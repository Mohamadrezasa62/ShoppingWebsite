# Internal events and development operations

This checkpoint extends R1/R9/R10/R11/R12 implementation. It does not accept
those milestones or enable live payments, external messaging or production.

## Migration and rollout

Back up the PostgreSQL database with the deployment's established backup
procedure before applying migrations. Apply all migrations before starting new
API/worker code: domain mutations now insert into `operations_outboxevent`.
Stop old workers for migration, run `python manage.py migrate`, then start API,
Celery workers and one beat scheduler. If migration fails, keep writes paused;
never downgrade a database with new financial records by deleting rows.

## Processing

The existing Celery worker discovers `operations.tasks.process_outbox` and
`catalog.tasks.check_product_alerts`. Beat scans product alerts every 60 seconds
and drains a bounded outbox batch every 10 seconds. Redis is required for the
broker and the persistent alert scan cursor. Internal catalog import jobs, campaign audience scans and in-app notifications
are handled; no SMS/email/push transport is connected.

Without a broker, process a bounded internal batch:

```bash
cd backend
python manage.py process_outbox --limit 100
```

Events are stored inside domain transactions, deduplicated by immutable event
key, and handled inside database transactions. Failure rolls back handler work,
retains the event and retries with bounded exponential delay. After five failed
attempts an event becomes `dead`. Inspect the system-administrator-only
processing panel, repair the cause, then replay with an audit reason. Replay
preserves the event key, so an existing notification cannot be duplicated.
Do not manually delete financial or event records to clear an error.

Monitor pending count, age, dead count, worker and beat health. The UI exposes
counts and timestamps; externally routed monitoring alerts remain a deployment
integration task. Error records store exception class only, never exception
messages or payloads containing customer addresses/payment credentials.

## Product subscriptions

Subscriptions require authenticated explicit consent and are one-shot in-app
alerts. A product qualifies only with a visible, approved-seller offer and free
stock after reservations. Price alerts fire at or below the requested threshold.
An alert is not a stock reservation or price guarantee. A subscription changed
or deleted before dispatch suppresses its previous generation's notification.
The keyset scan cursor resets at the end so large subscription lists are scanned
across successive jobs rather than starving later subscriptions.

## Verification and release gates

Run the backend suite from `backend/`; running plain test discovery from the
repository root can discover zero tests. CI explicitly names application labels.

```bash
cd backend
python manage.py test accounts catalog commerce operations sellers payments
python manage.py makemigrations --check --dry-run
cd ../frontend
npm run typecheck
npm run build -- --webpack
```

The ten PostgreSQL-only tests cover last-stock contention, duplicate checkout,
last coupon capacity, duplicate payment capture, concurrent refunds, account
closure racing with a new return, shared coupon budget contention, dispute
creation racing with payout, duplicate campaign-event processing and operational
hold creation racing with shipment. Their
SQLite skips are not passes. PostgreSQL/Redis/Compose, real browser flows,
load/restore rehearsal and provider verification must pass before launch.

Open external gates: repository write access; hosting/domain/storage; gateway
and SMS credentials/contracts; courier integration; KYC/bank verification;
financial/tax/return policies and accounting approval. Saved payment tokens,
loyalty/referral, multi-currency, native apps, multi-region deployment and
measured search/service extraction remain separate scope, not inferred from the
outbox implementation.

## Authored mobile browser flow

`frontend/tests/marketplace-e2e.cjs` drives Chromium at a mobile viewport: two
seller offers, customer cart/checkout UI, simulated capture, operator delivery
commands, customer return UI, simulated refund and anonymous isolation. The
browser CI job provisions PostgreSQL and Redis, builds Next, runs both servers
and invokes the flow. It does not exercise a real gateway or courier.

The development-only `seed_e2e` command requires both `DJANGO_DEBUG=1` and
`E2E_FIXTURES=1`. Use it only against a disposable test database. Its private
output file must be outside the repository, contains sessions valid for ten
minutes, and must be deleted after the run. Never publish it as an artifact.

```bash
python backend/manage.py seed_e2e --output /tmp/shopping-e2e-sessions.json
E2E_SESSION_FILE=/tmp/shopping-e2e-sessions.json npm --prefix frontend run test:e2e
```

Start backend on 127.0.0.1:8000 and the production frontend on 127.0.0.1:3000
with the CI environment first. Locally, browser installation failed because the
Chromium archive was truncated; this authored suite is not locally verified.

## Paid delivery cancellation

Customers can request cancellation of a complete seller delivery while it is
awaiting fulfillment or packing. Requested/approved cases block packing and
shipping under the same parent-order lock used by fulfillment. Marketplace
operators approve/reject with an audit reason; finance operators execute the
development-only sandbox refund. Rejection releases the hold. A delivery has
one case; re-submitting the same reason returns that case, and a different reason
is a conflict. There is no automatic expiry or individual-unit cancellation.

The refund uses checkout price/discount/shipping snapshots. Confirmed refund and
inventory restoration commit atomically and repeated execution cannot duplicate
either. Only that seller delivery is cancelled. Parent `paid` records the capture;
refund ledger entries describe cash returned independently. Seller payables have
not accrued for an unshipped delivery. Reports separate item and shipping refunds.
Production refuses this simulated refund; pending cases require operational
review and a verified real-provider refund integration before live use.

## Voluntary account deactivation

Customers request/withdraw account closure in their account page. Only a system
operator can complete or reject a pending request, with an audit reason. Staff
and seller-membership accounts require separate offboarding. Pending payment,
uncompleted delivery, unresolved return, cancellation or dispute blocks completion.
Checkout, seller onboarding and customer return requests use the same user-first
lock and recheck activity.
Completion deactivates the user, revokes sessions, disables marketing consent and product alerts, and
makes the password unusable. It does not erase the phone, addresses, orders,
support records or financial records and does not establish a retention period.
Legal erasure/anonymization and verified account reopening remain separate work.

## Structural checks after restore

Run against the restored, isolated database before enabling writes:

```bash
cd backend
python manage.py verify_commerce --output /tmp/restored-commerce-check.json
```

The command compares reserved stock with pending order quantities, order snapshot
totals with lines/shipping, capture records with attempts and paid orders, and
refund totals with captured cash. It never modifies data and returns a nonzero
exit code on mismatches, while retaining a report with at most 100 defect
references. It refuses to overwrite reports. Standalone PostgreSQL execution uses
a repeatable-read, read-only transaction; an existing caller transaction retains
its own isolation, reported explicitly. PostgreSQL execution is not verified here.

Review-required late captures are counted, not treated as structural corruption;
they still require provider reconciliation. Compare backup/restore counts and
cash totals with independently saved source evidence, then run business journeys.
These checks cannot prove backup completeness, recoverability, bank settlement
or certified accounting. Record restore duration, RPO/RTO and missing-provider
evidence separately. Do not auto-repair ledger or snapshots to silence a report.

## Followed catalog

Following a currently visible brand or approved seller stores a private customer
preference, capped at 100 targets. The `/following/` account page shows up to 24
currently available matching products. Suspended sellers, hidden brands, draft
products and unavailable offers are excluded by the normal public visibility
rules. Existing follows remain editable if their target later becomes unavailable.
Following does not enable marketing notifications or constitute message consent.
No external channel or implicit cross-site tracking is added.

## Order disputes and settlement holds

A customer may open one case per owned paid, non-cancelled seller delivery.
Repeating the same reason returns that case; a different reason conflicts.
The seller may respond once while the case is open. Support can read the staff
queue; only marketplace/system operators escalate, resolve or reject with an
explicit audit reason. Final decisions require a customer-visible resolution.
Internal notes stay out of customer/seller responses and customer exports.

Open, seller-responded and escalated cases exclude affected seller/order payables
from new settlements. Payout rechecks under seller/order locks, including cases
opened after settlement preparation. Already completed payouts cannot be undone
by opening a case: resolve the financial outcome through the refund/accounting
workflow. Closing a case does not itself refund cash, adjust a ledger or stop
shipping. One case cannot be reopened in this implementation.

## Consent-controlled in-app campaigns and coupon budgets

Customer marketing consent is off by default. Following, purchasing and receiving
transactional order notifications do not enable it. Consent changes rotate a
revision; queued messages from an older revision stay suppressed even after a
customer opts in again. Account completion disables consent.

Marketplace/system operators create drafts with a future end time and a public
relative product/collection/content link. Launch schedules scanning at the start
time. Audience scans reserve at most 100 recipients per batch and respect the
campaign's total recipient cap. `queued` means audience scanning ended, not that
all recipients received a message. Inspect delivered/skipped counts separately.
Each dispatch rechecks active account, time window, cancellation and matching
consent revision. Cancellation cannot retract a message already delivered.
There is no external SMS/email/push delivery or conversion tracking.

Coupon budget zero means unlimited. The budget counts discount snapshots for
pending and paid orders. Checkout serializes on the coupon row and rejects a
new discount exceeding the remainder; cart estimates do not reserve capacity.
Unpaid cancellation/expiry releases capacity. Refunds of paid orders do not
restore marketing budget automatically. This budget is a coupon discount cap,
not a general advertising spend ledger.

## Catalog CSV background jobs and exports

Use the catalog-import tab with catalog/marketplace/system staff permissions.
Download the template, replace category/brand references with active slugs and
submit UTF-8 CSV with the exact header order. Limits are 1 MiB, 250 rows and five
queued jobs per submitting operator. `attributes` and `specifications` are JSON
objects with bounded string keys/values. Every row creates a new product draft
and one variant; existing slugs/SKUs conflict. Import does not update products,
publish drafts, import media, create seller offers or change stock/prices.

The request UUID makes an identical file submission idempotent. A changed file
with the same UUID conflicts. Worker processing rechecks submitting staff access.
A known catalog/reference error rolls back all rows and records a bounded error
code plus logical CSV row number (header is row 1); the event itself completes.
Fix the conflicting catalog reference, then use audited job retry. A failed file
that needs editing must be resubmitted with a new UUID. Unexpected errors roll
back handler writes and use ordinary outbox retries; dead events can be replayed
or the job retried through a new generation, never by deleting records. A job
allows at most five generations. Older generation events become no-ops.

Successful jobs immediately clear source rows. Failed/queued sources remain for
retry; there is no automatic retention cleanup yet. Job APIs expose metadata,
errors and created product IDs, not the raw source. Review drafts using normal
catalog moderation before publication.

Staff CSV exports use variant-ID cursors and at most 250 rows per download.
Formula-like cells are prefixed with an apostrophe for spreadsheet safety.
Exports contain catalog metadata only, are not a consistent database backup and
are not an update/import round trip: identifiers already exist and escaped text
may differ. Continue with the returned cursor until zero; restart to begin anew.

## Purchase trust, customer images and support routing

The trust/review checkpoint uses three migrations: `sellers.0006`,
`catalog.0011` and `operations.0006`. Apply all before deploying API code because
fulfillment now reads risk cases under the parent-order lock.

Seller reviews require an owned, paid, delivered order and reject store members
rating their own seller. One review exists per delivery; repeated identical
payloads are idempotent. Support/marketplace/system operators moderate with an
audit reason. Suspension hides public seller ratings. Aggregates include only
published reviews; rating represents customer feedback, not a guaranteed SLA.

Review image access must remain API-controlled. Do not expose the media volume,
review-images directory or private object-store keys through an unrestricted
static/CDN route. Upload supports JPEG/PNG/WebP up to 5 MiB and 20 million source
pixels, normalizes orientation, bounds output dimensions and removes metadata.
The three-image quota includes withdrawn images to prevent repeated upload abuse.
Owners can preview pending/rejected images; only designated review moderators can
preview another customer's image. Public images require approved media, published
review and visible product/category/brand, checked at every request. Rejection or
withdrawal hides subsequent requests but cannot recall a copy already downloaded.
Withdrawal prevents staff republication; stored bytes are retained pending an
explicit retention/erasure policy. Upload audit failure rolls back the record and
removes the newly written file. Object-store lifecycle, orphan reconciliation and
retention cleanup are not implemented here.

Support routing lists active support/marketplace/system assignees without phones.
Escalation requires a marketplace/system manager assignee. Only managers can clear
escalation; resolve/close is rejected until then. Replies retain a previously
assigned owner. Queues prioritize escalation, then urgency, then update time.
Routing metadata and risk descriptions remain internal, absent from customer
order/ticket responses and owner exports.

## Manual order risk review

Marketplace/system staff create cases for pending/paid orders with an audit reason.
Support/finance can read the queue but cannot change cases. A request UUID dedupes
identical submissions and rejects changed payloads. At most ten open/escalated
cases per order are allowed. This is human review, not automated fraud detection.

An optional hold blocks new packing/shipping under the same order lock used by
fulfillment. A hold cannot be opened once all deliveries have shipped/completed.
It does not intercept payment capture, return processing or delivery confirmation
of an already dispatched parcel. Each open/escalated hold remains effective until
cleared; clearing one does not release another active hold.

Escalation preserves the hold. `clear` explicitly ends review and releases that
case's hold, for either dismissed or confirmed concerns. If a confirmed concern
requires cancellation, execute the order/cancellation workflow before clearing;
a confirmed outcome alone never cancels, refunds, blocks an account or rewrites
a payment/ledger. Record a resolution and reason. Cleared cases cannot reopen;
a new authorized case is required for a new concern. The authored risk/shipping
race test still needs PostgreSQL execution before live acceptance.

## Seller warehouse stock

Catalog migrations 0012–0014 add location stock and bootstrap existing offers.
Migration 0013 is irreversible: it validates aggregate stock and pending-order
reservations, then creates default warehouses, balances, bootstrap movements and
pending allocations. It fails on inconsistent source data rather than repairing
financial/stock records. Before deployment, pause old application writes and
workers, take a verified backup and rehearse on the actual PostgreSQL version.
The recorded 2,000-offer synthetic SQLite rehearsal does not satisfy that gate.
New seller offers and demo seed offers activate location inventory automatically.

Mutation lock order is actor user, seller, sorted offers, balances and warehouses
where applicable. Warehouse deactivation locks associated offers first, preventing
restock/deactivation races. The default location cannot be disabled; nonempty
locations cannot be disabled. Each seller is limited to twenty locations including
the default. Updates require a reason and appropriate approved store membership.
Never update cached offer totals or balance quantities directly in an admin shell.

Use location versions for physical stock corrections. A stale version returns a
conflict, including when checkout has reserved stock since an export. Stock CSV
imports are bounded, synchronous and atomic across all rows. Retain the request
UUID for retries; use a new key for a changed file. Legacy offer CSV or aggregate
stock PATCH cannot change multi-location totals. Transfers move only free units,
are immediate and do not model transport between warehouses.

Capture consumes the locations reserved by checkout. Cancellation/expiry releases
reservations; inspected returns and paid cancellation restore original logical
unit allocations once. Historical paid orders before activation restore to the
active default location using a legacy label. Inactive destinations reject restock
instead of silently relocating units. Shipping remains seller-level, not split
by warehouse. Run the commerce consistency checker to detect stock/cache/history
drift; investigate discrepancies without automatic repair.

Crossing from more than five free units to five or fewer emits an outbox event.
Only active store owners receive the in-app warning. Replays deduplicate, and
replenishment before processing suppresses stale warnings. No external transport
is claimed. See [R3/WAREHOUSE_INVENTORY.md](R3/WAREHOUSE_INVENTORY.md) for API limits
and outstanding PostgreSQL race evidence.

## Checkout approval and editorial imports

Apply commerce migration 0011 and catalog migrations 0015–0016 before deploying
the new code. The storefront sends ten-minute signed quote approvals. On estimate
expiry/change it refreshes prices and requires another customer confirmation;
do not automatically submit a refreshed amount. Keep the original checkout UUID
and token for transport retries. Legacy integrations may still omit approvals
for new orders; inventory/coupon recalculation remains mandatory.
See [R4/CHECKOUT_APPROVAL.md](R4/CHECKOUT_APPROVAL.md).

Catalog import jobs have explicit create/update modes. Update mode accepts only
revision-checked title, description and specifications. Run the outbox worker;
pending jobs recheck the submitter's authority. A stale row rolls back every change
in the file. Obtain a fresh update export rather than bypassing the revision or
changing the queued payload. Submission and per-product audits identify the
operator/reason and before/after content. See [R2/BULK_UPDATES.md](R2/BULK_UPDATES.md).

## Browsing-history retention

History is optional, owner-only, capped at fifty products and filtered to thirty
days on reads/exports. Disable or completed account closure deletes it immediately.
Keep Celery beat/worker running for hourly physical cleanup batches of 1,000 rows.
Expired data is excluded even when cleanup is delayed. Monitor expired-row backlog;
run additional `catalog.tasks.purge_expired_history` batches when necessary.
This does not enable external analytics or marketing consent. See
[R9/HISTORY.md](R9/HISTORY.md). Three new PostgreSQL contention tests for this
checkpoint remain required before release acceptance.

## Shipping methods and capacity windows

Commerce migrations 0012–0013 add method/window configuration and order snapshots.
Old deliveries receive the standard method label and no fixed window; historical
window data is not invented. New quote approval includes method/window details;
previously issued ten-minute tokens may require refresh after deployment.

Configure additional methods under each province/fulfillment rule in the shipping
panel. The fee is a full replacement, not a surcharge. Optional window capacity is
per seller delivery group. Quote previews never reserve it; orders do. Keep the
order-expiration worker running so abandoned checkouts release reservations.
Cancel/expire through domain services, not direct quantity or booking edits.

Booked window dates cannot be moved, including cancelled historical bookings.
Disable a window to stop new reservations without cancelling existing orders.
Capacity reductions cannot undercut live bookings. Past active windows are not
selectable; set them inactive before administrative edits. Checkout and admin
mutations use rule/method/window locks and audited transactions. Run the commerce
checker for excess booking capacity or shifted snapshots, then investigate without
automatic repair. The two new PostgreSQL races still require execution.

The feature does not contact couriers, certify physical dispatch capacity or
automatically reschedule late deliveries. Capacity is only for explicitly chosen
windows; no-window shipping remains available. See
[R4/SHIPPING_CHOICES.md](R4/SHIPPING_CHOICES.md) for contracts and limits.

## Customer order statements

Customers download their own statement from the order invoice route. The file
contains private recipient/address information and original purchase terms;
store or share it accordingly. Method/window, prices, discounts and addresses
come from order snapshots. Tracking and fulfillment status are current. After
refunds/cancellation the displayed purchase total remains the original total,
not an amount still due. The download is neither a tax invoice nor evidence of
capture. See R4/ORDER_STATEMENTS.md for tested scope and browser QA limitations.

## Configured category tax

Apply commerce migration 0014 before deploying this checkpoint. Existing orders
and returns receive zero tax snapshots; they are never repriced. Configure an
exact category under the admin tax tab only after reviewing the applicable
business policy. Rates use basis points (100 = 1 percent), apply after coupon
discount, and exclude shipping; parent category rules do not inherit. Disable a
rule to stop its future application. Old quote previews need refresh while
accepted checkout retries retain their original terms. Financial reports and
statements expose tax components but do not provide certified accounting or
jurisdiction filings. See R4/TAX_CONFIGURATION.md for refund rounding, schema
rollback limits and unverified PostgreSQL concurrency tests.

## Content versions and publication windows

Deploy operations migrations 0007/0008 before the updated content panel. Existing
pages receive version-1 baselines without inferred authors or publication
changes. PATCH integrations must now provide the latest version. On conflict,
preserve the unsaved text and fetch the new page before editing again. Restore
always creates an unpublished draft and clears schedules; review and explicitly
publish it after checking any slug collision. Dates follow the input device's
timezone and are sent as offset-aware instants. Public list/detail and sitemap
apply the same start-inclusive/end-exclusive window without a worker. Maintain
server clock synchronization and plan revision storage/retention. Refer to
R8/EDITORIAL_WORKFLOW.md for scope and rollback limits.

## OTP limits and staff password rotation

OTP request budgets are shared across login and staff-password challenges.
429 responses include Retry-After; successful consumption retains cooldown.
A staff password change requires the current password plus its dedicated OTP,
then invalidates all sessions. It is not a forgotten-password reset. Later DB or
audit failures roll back credentials but consume the OTP; wait for cooldown and
request another code. Cache outage returns 503 and prevents authentication.

The application trusts REMOTE_ADDR unless an explicitly configured trusted
peer supplies a single overwritten X-Real-IP. X-Forwarded-For is ignored;
NAT/CDN deployments may still share a budget. See R1/PRODUCTION_SMS.md and
validate the edge boundary and realistic traffic before launch. Counters assume available Redis
with appropriate capacity and synchronized clocks. CI uses its isolated Redis
service for AUTH_REDIS_TEST_URL; local Redis tests are not yet executed. The
Kavenegar adapter is implemented; approved credentials/templates and real
delivery verification remain outstanding. See R1/AUTHENTICATION_SECURITY.md for
limits, replacement-code semantics, rollback behavior and open acceptance work.
