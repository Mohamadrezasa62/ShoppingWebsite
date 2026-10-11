# Shipping methods and optional delivery windows

Staff shipping rules remain keyed by province and offer fulfillment mode.
Standard shipping (method ID zero) uses the existing rule fee/day range. Additional
methods have stable IDs/codes, labels, a full replacement fee and day range; their
fee is not added to the standard fee. Different seller deliveries can select
different methods. A method never changes the offer's seller/platform fulfillment.

## Customer contract

Quote query parameters `shipping_methods` and `shipping_slots` are JSON objects
mapping `sellerId:fulfillment` to method/window IDs. Omitted keys or zero use
standard shipping/no fixed window. The quote returns group keys, active method
options and available windows with remaining capacity. Available options are
estimates; a quote does not hold stock or a time window.

Checkout accepts the same objects together with `quote_token`. Nonempty selections
require signed approval. The digest covers selected method ID/code/label, full fee,
days and window ID/start/end, excluding changing remaining capacity. Checkout
rechecks availability and locks the chosen records. A changed selection under an
existing checkout UUID conflicts; original retries return the original order even
if the method/window later becomes inactive. The browser refreshes unavailable
options and requires customer confirmation again. A previously created order is
not silently charged with different shipping selections on a payment retry.

Order deliveries snapshot method code/label and window times. Customers see these
in orders; sellers/staff see them in fulfillment queues. An explicitly selected
absolute window takes precedence over the relative-day estimate in the UI.
The former snapshots remain intact after method price/label changes.

## Capacity and lifecycle

Capacity counts seller delivery groups, not item quantity, physical couriers or
warehouse units. Two sellers in one cart selecting the same window consume two
units. Windows are optional: selecting no fixed window does not consume a window
and is not a claim of overall carrier/warehouse throughput capacity.

The active booking count includes pending-payment and paid orders and excludes
cancelled deliveries. Cancellation/expiration releases capacity through order
state, without deleting history or counting release twice. Pending orders whose
expiry worker has not run conservatively continue to hold capacity. Payment
capture changes pending to paid and retains the same booking. Completed deliveries
retain their historical capacity use; past windows cannot be newly selected.

Slot locking and live counts serialize checkout. Account/offer/rule/method/window
locks follow a deterministic order, with user `NO KEY UPDATE` allowing audit FK
key-share locks. Admin changes lock actor, rule, method and window. Existing booking
dates are immutable even after all bookings cancel. Deactivation stops new
reservations while preserving existing orders. Capacity cannot fall below active
bookings. The consistency checker reports excess capacity and moved snapshots;
it does not repair bookings or change delivery promises.

## Staff API under `/api/v1/operations/`

| Endpoint | Methods |
|---|---|
| `shipping-rules/{id}/methods/` | GET methods, POST create |
| `shipping-methods/{id}/` | PATCH configuration |
| `shipping-methods/{id}/slots/` | GET latest 100 windows, POST create |
| `delivery-slots/{id}/` | PATCH window/capacity/active state |

Methods accept `code,label,fee_toman,min_days,max_days,is_active,reason` on create;
patch is a subset with a reason. Code `standard` is reserved. At most twenty
additional methods per rule are accepted, including inactive ones. A method's
parent rule cannot be changed. Historical records are not deleted through the API.

Windows accept `starts_at,ends_at,capacity,is_active,reason`. Datetimes must have
an explicit offset, start/end must be ordered, length at most twenty-four hours,
capacity 1–10,000, and active windows must be future and end within ninety days.
At most one hundred active future windows per method may be configured through
the API. The admin form uses device-local input converted to offset-qualified UTC.
Method identity cannot change; duplicate method/time pairs are rejected.

## Evidence and limits

Ten local tests cover snapshots/replay, price drift, province/ownership/active
checks, capacity per group, cancellation/expiry, timezone/input validation,
RBAC/CSRF, audit rollback, immutable booked dates and corruption detection.
Two PostgreSQL tests race buyers for the last slot and race a staff buyer's checkout
with window deactivation. They are authored, not locally executed. The complete
suite has 239 tests: 221 passed, 18 PostgreSQL tests skipped. TypeScript and
production webpack build passed; browser E2E remains unexecuted.

This is an internal scheduling promise, not a carrier integration, physical
capacity certification, route optimizer or dispatch guarantee. Overlapping
windows have separate configured capacities. The merchant must configure feasible
fees/dates/capacities. Missed-window alerts, rescheduling workflows, mandatory
window-only methods, live courier sync, tax, gift cards and guest checkout remain
outstanding; this checkpoint does not accept R4 or a production launch.
