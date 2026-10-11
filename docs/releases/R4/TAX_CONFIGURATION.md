# Configured category tax checkpoint

## Contract

Tax is explicit and exclusive of the offer price. No jurisdiction or legal rate
is assumed. Missing/inactive configuration means zero tax. Rules apply only to
an exact product category; there is no parent inheritance. Shipping is untaxed
in this implementation. Those limitations must be checked against an approved
business/tax policy before activating any production rule.

Staff with marketplace-manager/system-administrator authority use:

- `GET /api/v1/operations/categories/{id}/tax/`
- `PUT /api/v1/operations/categories/{id}/tax/`

PUT requires exactly label (1–160 characters), rate_bps (integer 0–10000),
is_active (boolean) and an audit reason. 100 basis points means 1 percent.
The existing CSRF protection applies. The operation rechecks authority inside
its transaction and logs before/after values; audit failure rolls back the rule.
The admin panel includes a dedicated category tax tab. There is no delete API;
deactivation preserves recorded order terms.

## Amounts and approval

First allocate the cart coupon using the existing exact integer allocation.
For each line, floor `(line_total - line_discount) * rate_bps / 10000` in toman.
Order tax is the sum of those per-line values; grand total is item total minus
discount plus shipping plus tax. The existing upper bound checks include tax.
There is no floating-point money arithmetic in the backend.

Quote lines return `tax: {rate_bps, label, amount_toman}`, and quote/order totals
include `tax_total_toman`. Immutable order lines store tax_toman, tax_rate_bps
and tax_label. The signed approval digest includes tax components. Changing
rate/label/applicability after preview requires new approval when the quoted
terms change. A completed checkout retry returns its original order snapshots.
Old, unconsumed quote tokens issued before this deployment must be refreshed;
accepted-order retries continue to validate their stored digest.

Checkout locks product rows in deterministic order before reading product and
category identity. Rule configuration and checkout share category-parent locks,
including when no tax rule exists yet. The account lock uses NO KEY UPDATE to
permit audit FK key-share locks. Preview reserves neither money nor inventory.
PostgreSQL concurrency results remain unverified locally.

## Refunds, finance and reports

Quantity returns allocate original net-item and tax components independently
across the same stable unit positions. All units add exactly to each original
component, including remainder toman. Confirmed return lines store
`tax_amount_toman`; refund amounts include both components. Paid cancellation
includes the original delivery tax, item net and shipping. Sandbox refund
retries remain idempotent. Real refund orchestration remains an external gap.

Seller payable and commission exclude tax. Return payable reversals subtract
the refunded tax before reversing seller net. Seller performance reports keep
item, tax and cancelled shipping components separate. Admin sales reports expose
paid-order tax and tax refunded through confirmed return/cancellation cases;
unallocated direct cash refunds are not inferred to be tax refunds. These
metrics are not a tax filing, liability general ledger or bank reconciliation.
Account exports and order statements include original tax snapshots. Statements
remain non-certified order documents even when tax is configured.

The read-only consistency checker validates line tax math, order totals and
unit refund components without modifying records. It does not retroactively
apply current tax rules to old purchases.

## Migration and verification

Commerce migration 0014 adds configuration and zero-default snapshots; existing
orders/returns are not repriced. Apply migrations before serving the new API.
Do not roll back the schema/code after taxed orders have been created without
an explicit compatibility/data plan.

Local checks: 256 tests discovered, 236 passed, 20 PostgreSQL-only tests skipped;
Django system checks/migration drift check passed; TypeScript and production
webpack build passed (25 static pages). Ten new SQLite tests cover coupons,
multiple categories/sellers, zero defaults, parent isolation, policy/product
changes, accepted retries, unit refund totals, seller payables, cancellation,
access/CSRF/audit rollback and deliberate snapshot corruption. Two PostgreSQL
race tests (rate edits and first-time rules vs checkout) are authored and skipped.
Browser UI/print QA, production tax policy, inclusive/shipping/location-specific
taxes, certified invoicing and jurisdiction reporting remain outstanding.

The existing local SQLite development database was migrated successfully through
0014. A read-only consistency check reported zero issues (two offers, zero
orders/payments); this is migration smoke evidence, not financial load evidence.
