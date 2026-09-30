# RTL experience and page sketches

Status: initial Milestone 1 wireframes. Detailed visual design and usability review remain open.

## Shared design rules

- Default language `fa` and direction `rtl`; layout starts from the right while product codes, email addresses and provider references retain their natural text direction.
- Start with a mobile layout and expand to desktop; cart totals and primary actions remain visible without obscuring content.
- Typography uses a legible Persian-capable font with system fallbacks. Font licensing and hosting are selected before release.
- Design tokens: primary `#dc2626`, text `#17202a`, muted `#667085`, surface `#ffffff`, background `#f6f7f9`, border `#e5e7eb`, success `#15803d`, warning `#b45309`, danger `#b91c1c`. These are initial tokens, subject to contrast review.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48 pixels. Minimum pointer target: 44 by 44 pixels.
- Every transactional state shows the next action and a clear error recovery path. Never imply that a payment succeeded until the server verifies it.

## Storefront: desktop concept

```text
┌───────────────────────────────────────────────────────────────────┐
│ logo   search products, brands...      location   account   cart │
├───────────────────────────────────────────────────────────────────┤
│ categories | offers | popular brands | help                      │
├───────────────────────────────────────────────────────────────────┤
│ campaign hero / rotating editorial placement                      │
├───────────────────────────────────────────────────────────────────┤
│ featured categories                                                │
├───────────────────────────────────────────────────────────────────┤
│ promotional offers      product cards with seller and delivery     │
├───────────────────────────────────────────────────────────────────┤
│ recommendations / popular products / trust and help links          │
└───────────────────────────────────────────────────────────────────┘
```

On mobile, search occupies a full row, categories become a scrollable strip, and primary navigation is reachable at the bottom. Campaign content must not delay access to search and cart.

## Product detail and offer choice

```text
breadcrumb
product title and rating
gallery          variant selector       purchase summary
                 key specifications     chosen seller, warranty
                 delivery by location   price, stock, add to cart
seller offers: seller | warranty | delivery | price | choose
description | specifications | reviews | questions
```

The selected variant changes the available offers. Each offer exposes its own warranty, stock, shipping source and final price. On mobile, the purchase summary becomes a sticky bottom action with a link to seller alternatives.

## Checkout

```text
cart → address → delivery groups and slots → payment → verified result
       each shipment shows seller, items, delivery promise and cost
       summary shows items + shipping − discounts = final total
```

The order may contain several shipments. A price or stock change is presented before payment and requires explicit acceptance. A pending payment result shows a verification state, not a success message.

## Seller portal

Dashboard highlights orders requiring action, stock alerts and settlement status. Navigation: products/offers, inventory, orders/shipments, returns, finances, store settings and support. Bulk uploads show accepted and rejected rows with reasons.

## Administrator portal

The landing page highlights payment verification failures, overdue shipments, pending seller/product approvals, returns awaiting a decision, and reconciliation mismatches. Navigation groups catalog, sellers, orders, payments/finance, campaigns/content, support/moderation, reports, staff/roles, audit and settings. Every high-impact action shows its effect and requires a reason; permissions determine which actions appear and the server enforces them.
