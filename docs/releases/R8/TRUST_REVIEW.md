# R8 / R11 purchase trust and operational review checkpoint

Date: 2026-10-11. Development implementation; no milestone acceptance.

## API contract

All endpoints below have `/api/v1/` prefix. Web authentication uses existing
session cookies and CSRF for every mutation. Public data has no buyer identifiers,
phones, addresses, bank fields or internal risk/routing descriptions.

| Route | Method | Access and behavior |
|---|---|---|
| `catalog/compare/?ids=1,2` | GET | Public; 2–4 distinct available product IDs; ordered comparison; all-or-error |
| `seller/public/{seller_id}/reviews/` | GET | Public approved seller; published count/average and latest 50 reviews |
| `seller/reviews/` | GET, POST | Owned review list; delivery/rating/body submission; one per delivery |
| `operations/seller-reviews/?status=pending` | GET | Support/marketplace/system review queue, max 100 |
| `operations/seller-reviews/{id}/decision/` | POST | Same roles; exact status/reason; audited publication or withdrawal |
| `catalog/my-reviews/` | GET | Owner's latest 100 product reviews and private media metadata |
| `catalog/my-reviews/{review_id}/images/` | POST | Owner multipart image/alt_text/request_key; max 3 total images |
| `catalog/review-images/{id}/preview/` | GET | Owner or designated review moderator; private normalized PNG |
| `catalog/review-images/{id}/` | GET | Public only after separate review/image approvals and current visibility |
| `catalog/review-images/{id}/withdraw/` | DELETE | Owner; permanent withdrawal from display, repeated call idempotent |
| `operations/review-images/?status=pending` | GET | Catalog/support/system image queue, max 100 |
| `operations/review-images/{id}/decision/` | POST | Same roles; exact status/reason; cannot reverse owner withdrawal |
| `operations/support-assignees/` | GET | Support/marketplace/system; active eligible staff IDs/display names |
| `operations/tickets/{id}/route/` | POST | Same roles; assignment/priority/escalation/reason, manager clears escalation |
| `operations/risk-cases/?status=open` | GET | Support/finance/marketplace/system; latest 100 internal cases |
| `operations/risk-cases/create/` | POST | Marketplace/system; order/request_key/category/severity/description/hold_fulfillment/reason |
| `operations/risk-cases/{id}/decision/` | POST | Marketplace/system; action/outcome/resolution/reason |

Money remains integer toman. Comparison starting price is the lowest currently
available offer, not a quote or a variant selection. Specifications are bounded
to 50 string entries per product. Selection URLs do not create customer tracking
records. Product visibility uses category/brand/product status and eligible offers.

## Verified local scenarios

- Seller reviews: delivered/paid gating, customer isolation, self-store rejection,
  repeat payload handling, publication, suspension, aggregate privacy, export,
  CSRF and audit failure rollback.
- Comparison: input bounds, order preservation, reservation-aware lowest price,
  hidden/missing product all-or-error behavior.
- Images: metadata removal, normalized PNG, owner/staff preview, duplicate upload,
  three-image quota, malformed files/UUID/CSRF, separate approvals, hidden brand,
  withdrawal preventing republication and record/file cleanup after audit failure.
- Operations: multiple risk holds, escalation and explicit release, dispatched
  delivery continuation, private descriptions, role restrictions, atomic audit;
  eligible support assignment, manager clearing, closure gate, preserved owner,
  prioritized queue and private routing metadata.

Full local suite: 180 discovered, 170 passed, 10 PostgreSQL-only skips. Next
TypeScript and production webpack build passed. Migration check found no drift.
The new risk/shipping PostgreSQL contention test is authored but not executed;
SQLite success does not demonstrate row-lock behavior. Browser interaction is
not verified locally. API tests use temporary media storage and no real customers.

## Remaining acceptance work

PostgreSQL/Redis and real browser execution, storage/CDN privacy review and lifecycle
cleanup, operational policy/training, richer editorial workflow and production
pilot remain open. Seller reviews do not replace KYC/performance verification.
Manual risk cases do not provide a scoring engine or automatically change money.
Account export includes owned review/media metadata, not internal case descriptions
or raw file keys. Account deactivation retains published feedback and stored
images under the still-open legal retention/erasure policy.
