# Bounded support history and queues

Development checkpoint; this does not establish live-chat or launch readiness.

## Read endpoints

- `GET /api/v1/operations/my-tickets/`: owner's queue.
- `GET /api/v1/operations/tickets/`: support-role staff queue.
- `GET /api/v1/operations/my-tickets/{id}/`: owner's conversation.
- `GET /api/v1/operations/tickets/{id}/`: support-role staff conversation.

Queues accept `page` (1–10000, default 1), returning 25 tickets, `page` and
`has_next`. Both accept `status=open|awaiting_customer|resolved|closed`. Staff
also accepts `priority=normal|high|urgent`, `assigned=mine|unassigned` and
`escalated=true|false`. Unknown/repeated parameters and invalid values return
400. Customer queue ties use descending ticket ID after last-update time. Staff
ordering retains escalation, priority and last-update precedence, with ticket ID
as the tie-breaker. Queue pagination uses offsets: a concurrent update can move
an item across pages. It is not a frozen queue snapshot; refresh to see changes.

Every ticket representation includes its newest **20 visible messages**, ordered
oldest to newest within the window. This replaces the previously unbounded
`messages` array in list and write responses. New fields `has_older_messages` and
`before_message` let callers request older history from the conversation endpoint
with `?before={before_message}`. This cursor filters message IDs strictly below
the supplied positive 64-bit integer. New messages do not shift older history;
there is no deletion endpoint. A terminal/empty window has `before_message: null`.
Clients that relied on complete history in one response must follow these links.

Customer reads exclude internal notes **before** slicing and cursor calculation,
so internal messages do not consume visible history slots. The owner restriction
runs on every history request; another customer's ticket returns 404. Staff
reads check current support-role access and may include internal notes.

## Query and UI behavior

Queue queries use a sliced Prefetch window per ticket, retaining at most 21
messages per candidate ticket (the extra item detects older history). Up to 26
ticket candidates detect the next queue page. This uses two domain queries for a
nonempty queue, independent of ticket count, rather than one message query per
ticket. Authentication/session queries are additional. Conversation reads use
one ticket query and one bounded message query. Full account exports remain
complete and exclude internal notes; queue limits do not truncate that export.

The support UI provides queue page controls, status and staff assignment filters,
manual refresh, and a per-ticket older-message button. Older messages are
prepended with ID deduplication. Refresh returns to newest message windows.
A load-generation guard prevents a previous queue/history response from
replacing the current queue after navigation or refresh. There is no polling,
websocket, presence or automatic real-time update claim.

## Validation and remaining work

Seven new behavioral tests cover complete public-history traversal, ownership and
internal-note isolation, malformed cursors, insert-stable history, fixed query
count/response limits, staff/customer filter restrictions and empty boundaries.
The SQLite suite validates window-prefetch behavior locally. PostgreSQL CI and
browser E2E execution remain outstanding, along with live transport, attachments,
external notifications and production support abuse policies.
