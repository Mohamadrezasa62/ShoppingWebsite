# Order statement checkpoint

The existing owner-only HTML download at
`GET /api/v1/commerce/orders/{id}/invoice/` now includes recipient/address
snapshots, separate seller deliveries, selected shipping method, optional
absolute delivery window, tracking, variant attributes, warranty, unit prices,
allocated line discounts, delivery totals and the original order total.

The download uses order/line/delivery snapshots rather than live catalog,
address or shipping configuration. Fulfillment status and tracking reflect the
current delivery state. It is an order statement, not a payment certificate,
tax invoice or outstanding balance after refunds. No legal tax policy is inferred; the subsequent category tax checkpoint adds configured tax snapshots (see TAX_CONFIGURATION.md).

Django template autoescaping protects all persisted customer/catalog text.
The download has no external assets or scripts and applies a restrictive CSP
including sandbox, no-referrer and nosniff. API middleware enforces no-store
(including 404/405 responses); authenticated non-owners, including staff, cannot
use the customer route. Staff access still uses existing operations routes.
The statement has responsive viewport, semantic tables and print styles;
visual browser/print verification remains outstanding.

Five regression tests cover owner isolation, snapshot stability, hostile text,
multi-seller coupon allocation and selected window/method stability. Statement
rendering uses three domain queries (order, deliveries, all lines), independent
of seller count; the test client additionally loads session and user.

Local verification: 244 tests discovered, 226 passed, 18 PostgreSQL-only tests
skipped. Django system checks and migration drift check passed. No model or
frontend changes. Production/browser acceptance and tax invoicing remain open.
