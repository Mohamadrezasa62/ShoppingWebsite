# Revision-checked catalog content updates

Authorized catalog/marketplace/system staff download
`GET /api/v1/operations/catalog-imports/update-export/?after_id={id}`.
The product cursor returns at most 250 rows with `X-Next-Product-ID` (zero at end).
Columns are exactly `product_id,revision,title,description,specifications`.
Spreadsheet formula prefixes in text are neutralized; review them before importing
an edited export. This export is distinct from the existing draft creation template.

Submit a multipart CSV to `/api/v1/operations/catalog-imports/` with `mode=update`,
`file`, `reason` and UUID `idempotency_key`. Files are UTF-8, at most 1 MiB/250 rows.
Identifiers and revision digests must remain unchanged. Duplicate rows, malformed
JSON, invalid text or revisions fail validation. Existing jobs default to `create`.
The same UUID/file/mode replays the job; a changed file or mode conflicts.

The outbox worker rechecks operator authority and locks products by ascending ID.
The revision hashes title, description, specifications, slug, category, brand and
status. Missing or interveningly changed products fail with row-level
`catalog_revision_conflict`; no earlier row or audit remains committed. A digest
describes content equality, not a monotonic change counter. An edit restored to its
original content is equivalent to the export.

Only title, description and specifications change. Slugs, category/brand,
publication, SKUs, options, price and inventory remain unchanged. Published product
content updates are immediately visible, like existing authorized single-product
edits; this does not add a second approval workflow. Historical order snapshots
remain independent. Every changed product has before/after audit data and a job
reference; the submission audit retains the operator's reason. Successful source
rows are discarded. Failed jobs retain bounded source rows for investigation and
up to five audited attempts. A stale file needs a fresh export/new request key;
retry never ignores its revision check.

Eight local tests passed, including late-row/audit rollback, deduplication, role
revocation, private export, validation and CSRF. One authored PostgreSQL test races
the worker with an individual edit; it remains unexecuted. Object storage/CDN and
media lifecycle deployment remain outside this checkpoint.
