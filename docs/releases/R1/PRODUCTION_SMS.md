# Production OTP transport candidate

The Kavenegar adapter implements the official SDK's HTTPS form POST to
`verify/lookup.json`, with receptor, token and template fields and `return.status`
200 acceptance. Source checked 2026-10-11:
https://github.com/kavenegar/kavenegar-python/blob/master/kavenegar.py

## Configuration and operator test

Keep `SMS_BACKEND=disabled` for infrastructure-only staging. To enable the adapter,
set `SMS_BACKEND=kavenegar`, `KAVENEGAR_API_KEY`, `KAVENEGAR_LOGIN_TEMPLATE` and
`KAVENEGAR_STAFF_PASSWORD_TEMPLATE` in the private environment file. Both template
names are mandatory and must be approved in the merchant's provider account,
using the `token` field for the six-digit code. Template identifiers currently
accept ASCII letters, digits, underscore and hyphen. Use your approved names;
the repository supplies no approved commercial template or real API key.
Restart API/workers after private settings changes and run deployment preflight.

With an authorized test phone, test customer login and staff password challenge
separately. Confirm messages arrive, wrong/expired/consumed codes are rejected,
and the provider's billing/approval behavior matches your contract. No real
message or provider transaction has been sent during this session. Unit tests
mock the HTTPS boundary; they do not prove actual delivery or account readiness.

## Failure and privacy behavior

Only the fixed provider host is contacted. Codes/phones/template values are in
POST bodies rather than query strings. The provider requires the API key in the
URL path; keep outbound proxy/APM URL logging disabled or explicitly redacted.
The app neither prints codes nor propagates provider URL/body/exception details.
HTTPS verification stays enabled, redirects are rejected, response bodies are
limited to 64 KiB and the socket timeout is eight seconds. No automatic retry:
a timeout can occur after provider acceptance, so blind retries may send twice.
This timeout is a socket timeout, not a guaranteed end-to-end deadline.

Any delivery failure invalidates its nonce while retaining cooldown and request
budgets. A delayed message for a failed submission therefore cannot log in.
Provider API status 200 means submission acceptance; carrier delivery is not
claimed. Transport status receipts, credit monitoring, external alerting and
provider fallback remain separate work.

## Trusted edge identity

The production Compose edge uses fixed private address `172.30.91.10` on subnet
`172.30.91.0/24`. `AUTH_TRUSTED_PROXY_NETWORKS=172.30.91.10/32` permits only that
peer to supply a single `X-Real-IP`; Caddy **overwrites** that header from its
connection's remote host. X-Forwarded-For is ignored. Other containers/direct
requests cannot choose a throttle identity using forwarded headers.

Check this subnet does not overlap host/VPN networks. If changing it, update the
Compose subnet, edge IP and auth trust setting together. Existing networks may
need recreation during a write-paused release; preserve data volumes. Never
trust all addresses or allow public direct API access. A CDN/load balancer in
front of Caddy currently becomes the reported client: do not reuse arbitrary
forwarded headers; design and test its additional trust boundary first.

Missing/malformed trusted client headers share an unknown-client bucket; invalid
proxy-network configuration fails authentication closed. IPv4-mapped IPv6 is
normalized. Different clients behind the edge receive independent budgets;
actual NAT clients can still share an IP. Eleven tests cover transport contracts,
redaction, timeout/no retry, validation, invalidation/cooldown, redirects and trusted
proxy identity/budget isolation. Real Redis/edge/load evidence remains required.
