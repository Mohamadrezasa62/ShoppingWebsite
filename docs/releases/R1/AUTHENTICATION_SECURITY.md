# Authentication hardening and staff credential rotation

## Shared-cache abuse limits

Valid OTP request operations share a peer-IP budget of 20 requests per fixed
10-minute window and 100 per fixed hour. Login verification and staff password
change share 100 attempts per peer per fixed 15-minute window. Phone requests
also share the existing 60-second cooldown and five requests per hour across
both code purposes. Responses use 429 and Retry-After in seconds. Fixed windows
can allow adjacent-window bursts; these are application budgets, not a WAF,
distributed attack defense or production load/security acceptance.

Peer identity uses normalized REMOTE_ADDR hashed with the application secret.
Configured trusted peers may supply one validated X-Real-IP, overwritten by the
edge. Arbitrary X-Forwarded-For and headers from untrusted peers are ignored.
Unknown clients share a bounded fallback bucket. See PRODUCTION_SMS.md for the
fixed edge network, direct API isolation and remaining real traffic validation.

Counters use expiring bucket keys and shared-cache add/incr. Production settings
use Redis; LocMemCache is only the existing SQLite test/development substitute.
Cache failures during these paths return 503 authentication_unavailable rather
than permitting authentication or creating a new account. Redis eviction or
manual cache clearing can reset budgets; production Redis availability and
capacity remain operational requirements.

## One-time code semantics

Login and staff-password codes use different cache scopes and keyed digests.
Provider delivery receives the purpose; console delivery labels it and remains
permitted only with DEBUG. Neither code can verify the other operation. The
verification service returns the validated challenge nonce, and final consumption
must match that exact nonce and code. Even an identical replacement code cannot
be consumed by a confirmation bound to the older nonce.

Atomic cache add marks one nonce consumed once. Successful consumption retains
the expiring code record and cooldown instead of deleting them. An in-flight
old consumer can complete without deleting a replacement record; failed SMS
delivery invalidates its own nonce without deleting a newer challenge. Consumed
records cannot verify again. Codes expire after five minutes and permit at most
five verification attempts. Login now locks the current user while rechecking
staff password/active state; failed final consumption rolls back newly created
accounts. Kavenegar transport is implemented; provider credentials/template approval and
real delivery verification remain outstanding.

## Staff password workflow

Authenticated active staff use:

- `POST /api/v1/auth/staff-password/request-code/` — sends the dedicated code
  to the current account phone, subject to shared phone/peer budgets.
- `POST /api/v1/auth/staff-password/change/` — requires exactly current_password,
  new_password and code, with CSRF. Password inputs are bounded to 1024 characters.

The endpoint rechecks active/staff status under the user row lock, checks the
current password and dedicated code, rejects unchanged passwords and runs the
configured Django password validators. It stores the new password hash,
increments session_version and creates an audit event in the same transaction.
Audit metadata never contains password input, password hashes or OTPs. Success
logs out the caller; other devices become unauthenticated through existing
password/session-version checks. The account UI exposes this workflow only for
staff. Forgotten-password recovery, first-password provisioning and phone/SMS
recovery are not provided by this rotation endpoint.

Cache consumption is not part of the database transaction. If a later database
or audit write fails, password/session changes roll back but the code remains
consumed. Request a fresh challenge after the cooldown. If a success response is
lost, verify login with the new password instead of assuming the change failed.

## Verification

Latest local suite: 286 tests discovered; 261 passed and 25 skipped (23 require
PostgreSQL, two require an isolated Redis integration URL). Thirteen new SQLite
behavior tests cover purpose isolation, peer limits and spoofed headers, cache
outage behavior, nonce replacement, delivery failure, credential validation,
CSRF/access, audit rollback, account-creation rollback and session invalidation.
TypeScript and production webpack build passed (25 static pages). Django checks
and migration drift check passed; no new model migration is needed.

One PostgreSQL authority/demotion race and two Redis parallel nonce/counter tests
are authored but unexecuted locally. Set AUTH_REDIS_TEST_URL to an isolated Redis
instance to run the latter; they use unique prefixes and do not flush it. The
backend CI job now supplies its Redis service database 1 for those tests. CI has
not been executed in this session. Real SMS, proxy/edge configuration, Redis/PG
results, browser acceptance, security review and production pilot remain open.
