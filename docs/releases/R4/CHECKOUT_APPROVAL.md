# Checkout approval contract

`GET /api/v1/commerce/quote/?address_id={id}` returns an owner-only, uncached
estimate and current line prices. A ready quote includes `approval_token` and
`valid_for_seconds: 600`. The signed token includes version, user/address IDs and
a SHA-256 digest; it does not contain contact details, address text or raw cart
snapshots. The token is an approval of the estimate, not a price or stock reservation.

The storefront sends `quote_token` with `address_id` and `idempotency_key` to
`POST /api/v1/commerce/checkout/`. Checkout locks the account, cart, address,
offers, shipping rules and coupon, then recalculates and compares the digest
before creating an order or reserving stock. Address, cart line IDs/quantities,
offer prices/warranty/fulfillment, seller/commission snapshot, product title/options,
shipping rule/fee/days and coupon identity/discount are included.

`quote_changed`, `quote_expired` or `invalid_quote` leave cart/stock untouched.
The UI refreshes the estimate and requires another button press. Availability and
coupon eligibility are checked again independently. Prices/fees beyond the total
storage limit never receive an approval token. Changing an address cancels an old
preview request in the client, preventing a late response from replacing the new
selection. Individual current unit prices appear beside the approval action.

An accepted order stores its approval digest. Repeating its original UUID and
signed approval returns the original order, including after ten minutes or after
the cart has been emptied. Changed approvals conflict with that UUID. Tokens
remain bound to owner/address. Missing approval on an approved order cannot bypass
this replay check. Legacy callers that omit `quote_token` for a new order still
recalculate at confirmation; migrate those callers before mandating the field.

The account lock uses PostgreSQL `NO KEY UPDATE`, allowing audited shipping-rule
changes by the same staff buyer to take an actor FK key-share lock while checkout
serializes account writes. A contention test is authored; SQLite does not verify
this lock behavior. Eight local approval tests passed, including multi-seller fee/line agreement. Existing checkout/payment,
inventory, coupon and refund regression tests remain in the complete suite.

Tax, selectable delivery methods/slots, gift cards and guest checkout remain
incomplete. No domestic tax rate, gateway agreement or production acceptance is
invented. Real provider verification remains mandatory before a live paid order.
