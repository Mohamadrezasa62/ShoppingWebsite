# Optional recently viewed products

Browsing history is owner-only and off by default. The account page links to
`/recently-viewed/`, where customers opt in, opt out or clear history. Product pages
record a view only after the authenticated profile indicates enabled history.
The server rechecks the preference under the same account lock used by disabling
and account deactivation; a stale browser cannot recreate disabled history.

| Endpoint under `/api/v1/catalog/` | Contract |
|---|---|
| `GET history/` | Preference, limits and current visible product cards in recency order |
| `PATCH history/` | Exact JSON `{"enabled": true/false}`; false deletes history |
| `DELETE history/` | Clear records while keeping the preference |
| `POST history/views/` | Exact JSON `{"product_id": id}`; disabled returns `recorded: false` |

Mutations require authentication and CSRF. Records have one row per account/product,
retain only the fifty newest products and expose no buyer history to staff/sellers
through these endpoints. Products hidden by catalog policy or without current
available offers are excluded from cards. View recording accepts only public
products. Clearing is immediate; completed voluntary account deactivation also
disables and deletes this activity transactionally.

Reads and account exports exclude records older than thirty days. Celery beat
enqueues `catalog.tasks.purge_expired_history` hourly, deleting at most 1,000 expired
rows per run and rechecking expiry to avoid deleting a refreshed row. Physical
deletion can lag the visibility cutoff if workers/beat stop or the backlog exceeds
that batch; monitor it and drain additional batches as needed. No browser anonymous
history, external analytics, advertising consent or marketing transport is enabled.

Six local tests passed for consent, owner isolation, deduplication/cap, ordering,
visibility, expiration/export, cleanup, CSRF and deactivation rollback. One
PostgreSQL opt-out/view contention test is authored but unexecuted. This is private
shopping convenience, not recommendation personalization or funnel analytics.
