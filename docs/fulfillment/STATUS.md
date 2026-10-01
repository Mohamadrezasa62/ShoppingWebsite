# Fulfillment milestone status

Milestone 8 now has delivery state and tracking fields, a private transition
service that requires a paid order, a buyer return request model, and a ledger
guard that prevents verified refunds from exceeding captured money. These paths
have automated tests. They are not yet exposed as complete seller, buyer, or
staff workflows.

Remaining work: authenticated role-scoped shipment actions, buyer tracking and
notifications, cancellation and stock/finance effects, return evidence and
authorization, certified provider refund initiation and reconciliation,
support queues, and delivery and return reporting. Live end-to-end tests depend
on a certified payment adapter from Milestone 7.
