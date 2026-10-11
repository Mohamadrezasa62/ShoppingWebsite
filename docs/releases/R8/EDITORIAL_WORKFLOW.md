# Content revision and publication-window checkpoint

## Staff workflow

The content panel now edits existing title/slug/body/kind, publication flag and
optional start/end times, previews current text privately, lists revision
history and restores historical text. Content remains plain text, rendered as
text by React rather than executable HTML. Changing a slug does not create a
redirect. Editing a currently visible page changes its public text immediately;
turn publication off to edit an unpublished draft. This checkpoint does not
provide a parallel draft alongside a live version or a two-person review gate.

Existing catalog-operator/marketplace-manager/system-administrator roles retain
editorial access. Mutations require CSRF, a reason and an in-transaction authority
recheck. Account NO KEY UPDATE then page-row locks serialize edits and allow audit
FK key-share locks. Page, revision and audit writes commit together. Audit failure
rolls back the full operation. Revision model saves reject replacing an existing
snapshot; direct database/queryset writes are outside that service guarantee.

## API contract

- `GET /api/v1/operations/pages/?page=1` returns 25 private pages, page/has_next;
  page is an integer 1–10000. This replaces the old truncated 100-row list.
- `POST /api/v1/operations/pages/` creates a page and its first revision.
- `PATCH /api/v1/operations/pages/{id}/` requires the current positive integer
  `version`, plus editable fields and reason. Stale versions return 409
  `content_version_conflict`; missing/invalid versions return 400. Legacy PATCH
  callers must fetch and send the version; the bundled frontend is updated.
- `GET /api/v1/operations/pages/{id}/revisions/?before=26` returns at most 25
  snapshots with metadata and a next_before cursor. History is role-restricted
  and no-store. Snapshots are scoped to a single page.
- `POST /api/v1/operations/pages/{id}/restore/` requires version,
  restore_version and reason. It creates a new monotonically numbered revision
  with the historical title/slug/body/kind, unpublished and without a schedule.
  It does not remove/rewrite later history or reactivate historical publication.
  Reused slugs can conflict and roll back the restore.

A successful edit creates a new revision even if values are unchanged. The
version is an optimistic concurrency counter, not a content fingerprint.
Old-editor edits and stale restores cannot overwrite a newer page. Revision
metadata includes capture time, actor ID and reason; it is never public.

## Scheduling and discovery

Staff dates require ISO datetimes with an explicit UTC offset, or null. If both
bounds exist, end must be strictly after start. The UI accepts device-local
wall time and sends an ISO instant; display/input timezone follows the device.
A page is visible only when is_published is true, start is absent or <= request
time, and end is absent or > request time. At the exact start it becomes visible;
at the exact end it becomes unavailable. Draft flags override all schedules.

The shared visibility query gates public list, slug detail and sitemap feed.
The existing frontend content fetch and sitemap are dynamic/no-store. No worker
must successfully run for start/expiry visibility to take effect. Already loaded
browser content, external caches/copies and search-engine removal timing are not
revoked by this query. Server clocks must remain synchronized.

## Migration, verification and remaining scope

Apply operations migrations 0007 and 0008 before deploying the API/UI. Existing
pages receive version 1, empty time bounds and a truthful baseline snapshot with
no inferred author. Migration preserves body and publication state; capture
creation time is not an invented original edit time. Revision retention is not
automatically pruned; storage sizing and approved retention policy remain open.
Rolling back schema after editing discards revision history and schedule fields;
do not treat that as a history-preserving rollback.

Latest local result: 270 discovered tests, 248 passed, 22 PostgreSQL-only tests
skipped. Eleven new SQLite behavior tests cover schedule boundaries and sitemap,
version conflicts, restores, privacy, CSRF, validation, audit rollback and both
pagination flows. One migration test checks existing-page baseline preservation.
Two PostgreSQL races (edit/edit and edit/restore) are authored but unexecuted.
Django checks and migration drift checks passed. Frontend TypeScript and
production webpack build passed with 25 static pages. Browser UI acceptance and
PostgreSQL results are not claimed. Review approval, parallel live/draft versions,
redirect governance, rich media/editorial blocks and retention remain separate.
