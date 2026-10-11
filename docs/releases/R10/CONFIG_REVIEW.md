# Local production-configuration review

2026-10-11. No deployed environment or launch approval is represented here.

Executed `python manage.py check --deploy` with `DJANGO_DEBUG=0`, a fresh
ephemeral strong secret, console SMS disabled and sandbox payments disabled.
The secret was neither logged nor committed. This local review used SQLite and
did not contact a production database, Redis, provider, domain or TLS proxy.

The command exited 0 with two warnings:

| Check | Open configuration |
|---|---|
| `security.W004` | HSTS duration is not configured |
| `security.W008` | HTTPS redirect is not enabled |

Exit 0 does not mean warning-free deployment readiness. Configure TLS/domain
and the trusted proxy in the actual environment, decide HSTS for that domain,
set `DJANGO_SECURE_SSL_REDIRECT` and `DJANGO_HSTS_SECONDS` as appropriate, then
rerun checks and verify redirect/secure-cookie behavior through the real proxy.
The ephemeral secret must never be used as a deployment credential.

Locally verified: Django tests, migration drift check, frontend TypeScript/build,
synthetic catalog profiling and structural financial check behavior, including
failure injection. Unverified: PostgreSQL/Redis execution, browser E2E, provider
certification, worker saturation, restore rehearsal, security/load/accessibility
review and live pilot. The authored CI requires repository write access to run.

`verify_commerce` supplies structural evidence after a restore; it neither performs
a backup nor substitutes for recovery/pilot evidence. See the operations runbook.
