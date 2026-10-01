# Launch readiness review

Date: 2026-10-01. This is a gate record, not launch approval.

## Checks run on the current branch

- Backend: 43 tests passed on local SQLite; migrations have no pending model changes.
- Frontend: TypeScript check and production build passed.
- Docker Compose configuration parses. Docker Engine is unavailable on this
  workstation, so the stack and PostgreSQL behavior have not been exercised here.
- Django deployment check reports `security.W004` (HSTS not configured) and
  `security.W008` (HTTPS redirect not configured). These require the actual
  domain and trusted TLS proxy configuration before production rollout.

## Release gates still open

1. Complete Milestones 1–9 acceptance, including seller, admin, checkout,
   payment, fulfillment, and promotion workflows.
2. Obtain provider merchant agreements, signed specifications, credentials,
   sandbox certification, and a successful live payment and refund pilot.
3. Deploy behind trusted HTTPS termination, configure Django host and CSRF
   origins, confirm secure cookie behavior, decide HSTS after domain validation,
   and rerun `manage.py check --deploy` without warnings.
4. Replace the development API server and bind-mounted source Compose setup
   with a production deployment design, persistent media storage, secret
   management, monitored workers, and tested database backups.
5. Rehearse backup and restore in a separate environment; record restore time
   and data integrity evidence. Run load, browser, mobile, accessibility, RTL,
   and security tests. Close critical findings.
6. Run a seller pilot and representative buyer journeys including cancellation,
   partial refund, late payment, and support escalation. Assign on-call and
   operational owners, and record incident and rollback procedures.

Milestone 10 remains open. No production launch is authorized by this record.
