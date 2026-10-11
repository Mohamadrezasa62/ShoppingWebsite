# HTTPS infrastructure deployment candidate

This is a **staging deployment candidate**, not a completed marketplace launch.
Latest local application verification: 336 passed, 30 integration skips; frontend typecheck, production build and payment redirect checks passed. See IMPLEMENTATION_STATUS.md for scope.
A local standalone Next + DEBUG=0 Django/SQLite runtime smoke passed HTTP
redirect, trusted-TLS readiness, SSR collections and HTTPS sitemap origin. This
does not substitute for containers, a real TLS certificate or PostgreSQL. Docker/Caddy/PostgreSQL/Redis stack
execution is authored in CI but has not run in this session; Docker and Caddy
are unavailable here. No host, domain, credentials or actual deployment is supplied.

## Prerequisites and configuration

Use a dedicated Linux host with Docker Engine and Compose v2 supporting profiles,
health dependencies and `up --wait`. Point the actual site hostname at it and open
80/443 for Caddy's ACME/TLS. Preserve database, uploads, static assets, Redis,
beat and Caddy volumes. Review image/dependency versions and resource sizing.
The standalone `compose.production.yaml` must **not** be overlaid on the
bind-mounted development compose file. It exposes only Caddy's 80/443 ports;
PostgreSQL, Redis, API and frontend have no published host ports. Keep the private
Docker network isolated; proxy trust depends on this boundary.

```bash
cp deploy/production.env.example .env.production
chmod 600 .env.production
```

Replace every placeholder with the reviewed git SHA, real hostname/operator
email, random Django secret (at least 50 characters) and database password.
Set SITE_URL and CSRF origin to the same HTTPS origin, and ALLOWED_HOSTS to the
site hostname plus `api` (internal readiness/server rendering). Never commit
this file, print `docker compose config` with secrets, or publish CI secret files.
The preflight command checks configuration without printing secret values.

The backend container runs as UID/GID 10001 and the frontend as `node`, with no
source bind mounts. New named volumes inherit directory ownership from the
image. Existing media/static/beat volumes may require operator-reviewed ownership
migration; preflight detects inaccessible media/static directories. Never solve
permission issues by making uploads world-writable. Frontend runtime contains
standalone output, static assets and public files rather than build dependencies.

## First staging release

Run from the repository root:

```bash
docker compose --env-file .env.production -f compose.production.yaml config --quiet
docker compose --env-file .env.production -f compose.production.yaml build api frontend
docker compose --env-file .env.production -f compose.production.yaml up -d --wait db redis
docker compose --env-file .env.production -f compose.production.yaml run --rm release
docker compose --env-file .env.production -f compose.production.yaml up -d --wait api worker beat frontend edge
```

The one-off release job checks settings, applies migrations, seeds **roles only**,
collects admin static assets, and checks DB, migration plan, roles, Redis and
shared storage. It creates no demo users/staff credentials/payment records. The
API process runs Gunicorn directly; restarting it never runs schema migrations.
Run only one beat instance. A failed release must stop rollout. This sequence is
for a fresh staging instance; it does not authorize an online destructive upgrade.

Check `https://your-host/health/`, `/ready/`, `/collections/`, `/sitemap.xml`, admin
static assets and moderated media. `/health/` is process liveness; `/ready/` executes
an actual DB query and Redis round trip but does not establish worker health,
schema completeness or external-provider availability. The release preflight
checks migrations separately. Do not invent worker-health results from readiness.

Caddy routes `/api/*`, `/admin/*`, `/health/`, `/ready/` directly to Django, replacing
TLS headers. `/static/*` serves collected assets; raw `/media/*` returns 404.
Product/review media stays behind existing visibility/ownership endpoints.
Server-rendered Next requests use `API_INTERNAL_TLS=1` to mark trusted internal
requests as HTTPS after TLS termination; otherwise Django's secure redirect
would point the internal HTTP request at an unavailable HTTPS backend.

## Upgrading and rollback

Before an upgrade, pause ingress/write traffic and stop API/worker/beat, take an
off-host PostgreSQL backup plus uploads/config/Caddy backup, and rehearse restore
against a disposable database. Follow [operations migration notes](OPERATIONS_RUNBOOK.md),
especially irreversible inventory bootstrap and financial snapshots. Build/tag
reviewed images, run the release job while writes remain paused, inspect consistency
reports, then restart the stack and verify before reopening traffic.

Code-only rollback requires a known compatible schema and retained prior images.
Do not reverse migrations or restore a stale financial database after new real
payments without reconciliation. A failed migration remains an incident with
writes paused. No restore/rollback success is claimed in this checkpoint.

## Launch gates

`python manage.py deployment_preflight --launch` intentionally fails: this repo
has default-off Zarinpal creation/verification but no certified live payment
acceptance/reconciliation or real refund/payout adapters. See R5_ZARINPAL.md and R5_PAYMENT_RECOVERY.md for creation, verification and
customer/finance recovery. A Kavenegar OTP adapter
is now implemented, but real delivery/templates/account approval are unverified. Disabled
SMS means customers cannot obtain login codes. Console OTP and sandbox money are
forbidden with DEBUG=0. Configuration strings cannot substitute for integrations.
This stack is suitable for infrastructure rehearsal, not taking real orders.

Before public commerce: implement/certify providers; approve tax, invoicing,
KYC/bank, return/refund and settlement policies; execute PostgreSQL contention,
Redis, browser E2E, HTTPS stack, migration/load/security and backup-restore tests;
configure monitoring/alerts and media retention; complete applicable remaining
features in IMPLEMENTATION_STATUS.md. The edge now overwrites client IP and uses a fixed trusted private address,
so OTP client budgets are separated. Verify subnet/trust boundaries and
realistic abuse/load behavior before enabling real SMS. See
[R1/PRODUCTION_SMS.md](R1/PRODUCTION_SMS.md) for credentials, templates and limits.

The deployment-smoke workflow builds images, validates Compose/Caddy, starts a
disposable DB/Redis stack, runs release preflight and checks API readiness plus
server-rendered collections. It does not obtain real TLS certificates or contact
providers. The workflow is authored and not yet executed on GitHub here.
