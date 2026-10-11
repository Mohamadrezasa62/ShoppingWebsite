"""Read-only commerce consistency checks; never auto-repair financial records."""
from django.db import connection, transaction
from django.db.models import F, OuterRef, Subquery, Sum, Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from catalog.models import Offer, Warehouse, StockBalance, StockReservation, StockMovement
from commerce.models import Order, OrderLine, OrderDelivery, DeliverySlot, ReturnLine
from payments.models import LedgerEntry, PaymentAttempt


def inspect_commerce():
    outer_transaction = connection.in_atomic_block
    issues, issue_count = [], 0
    def issue(code, reference):
        nonlocal issue_count
        issue_count += 1
        if len(issues) < 100:
            issues.append({"code": code, "reference": reference})
    with transaction.atomic():
        # Avoid a mixed-time inventory/order view while checkout runs concurrently.
        if connection.vendor == "postgresql" and not outer_transaction:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        slot_bookings = OrderDelivery.objects.filter(shipping_slot_id=OuterRef("pk"), order__status__in=("pending_payment", "paid")).exclude(status="cancelled").values("shipping_slot_id").annotate(total=Count("pk")).values("total")
        for row in DeliverySlot.objects.annotate(booked=Coalesce(Subquery(slot_bookings), 0)).values("pk", "capacity", "booked").iterator(chunk_size=500):
            if row["booked"] > row["capacity"]:
                issue("delivery_slot_capacity_exceeded", f"slot:{row['pk']}")
        for row in OrderDelivery.objects.filter(shipping_slot__isnull=False).values("pk", "delivery_window_start", "delivery_window_end", "shipping_slot__starts_at", "shipping_slot__ends_at").iterator(chunk_size=500):
            if (row["delivery_window_start"], row["delivery_window_end"]) != (row["shipping_slot__starts_at"], row["shipping_slot__ends_at"]):
                issue("delivery_window_snapshot_mismatch", f"delivery:{row['pk']}")
        reservations = OrderLine.objects.filter(offer_id=OuterRef("pk"), delivery__order__status="pending_payment").values("offer_id").annotate(total=Sum("quantity")).values("total")
        for row in Offer.objects.annotate(expected=Coalesce(Subquery(reservations), 0)).values("pk", "available_quantity", "reserved_quantity", "expected").iterator(chunk_size=500):
            if row["reserved_quantity"] != row["expected"] or row["reserved_quantity"] > row["available_quantity"]:
                issue("reservation_mismatch", f"offer:{row['pk']}")
        stock = StockBalance.objects.filter(offer_id=OuterRef("pk")).values("offer_id")
        stock_total = stock.annotate(total=Sum("quantity")).values("total")
        stock_reserved = stock.annotate(total=Sum("reserved_quantity")).values("total")
        stock_count = stock.annotate(total=Count("pk")).values("total")
        for row in Offer.objects.filter(inventory_managed=True).annotate(physical=Coalesce(Subquery(stock_total), 0), allocated=Coalesce(Subquery(stock_reserved), 0), balance_count=Coalesce(Subquery(stock_count), 0)).values("pk", "available_quantity", "reserved_quantity", "physical", "allocated", "inventory_activated_at", "balance_count").iterator(chunk_size=500):
            if row["inventory_activated_at"] is None or not row["balance_count"] or (row["available_quantity"], row["reserved_quantity"]) != (row["physical"], row["allocated"]):
                issue("warehouse_cache_mismatch", f"offer:{row['pk']}")
        allocation = StockReservation.objects.filter(balance_id=OuterRef("pk"), status="reserved").values("balance_id").annotate(total=Sum("quantity")).values("total")
        changes = StockMovement.objects.filter(balance_id=OuterRef("pk")).values("balance_id")
        physical_changes = changes.annotate(total=Sum("quantity_delta")).values("total")
        reservation_changes = changes.annotate(total=Sum("reserved_delta")).values("total")
        for row in StockBalance.objects.annotate(allocated=Coalesce(Subquery(allocation), 0), physical_history=Coalesce(Subquery(physical_changes), 0), reserved_history=Coalesce(Subquery(reservation_changes), 0)).values("pk", "quantity", "reserved_quantity", "allocated", "physical_history", "reserved_history", "warehouse__seller_id", "offer__seller_id", "offer__inventory_managed", "warehouse__is_active").iterator(chunk_size=500):
            if not row["offer__inventory_managed"] or row["warehouse__seller_id"] != row["offer__seller_id"]:
                issue("warehouse_offer_ownership_mismatch", f"balance:{row['pk']}")
            if row["reserved_quantity"] != row["allocated"] or (row["quantity"], row["reserved_quantity"]) != (row["physical_history"], row["reserved_history"]):
                issue("warehouse_history_or_reservation_mismatch", f"balance:{row['pk']}")
            if not row["warehouse__is_active"] and row["quantity"]:
                issue("inactive_warehouse_has_stock", f"balance:{row['pk']}")
        line_allocations = StockReservation.objects.filter(order_line_id=OuterRef("pk")).values("order_line_id").annotate(total=Sum("quantity")).values("total")
        required_lines = OrderLine.objects.filter(offer__inventory_managed=True).filter(Q(delivery__order__status="pending_payment") | Q(delivery__order__created_at__gte=F("offer__inventory_activated_at"), delivery__order__status="paid"))
        for row in required_lines.annotate(allocated=Coalesce(Subquery(line_allocations), 0)).values("pk", "quantity", "allocated").iterator(chunk_size=500):
            if row["quantity"] != row["allocated"]:
                issue("warehouse_line_allocation_mismatch", f"line:{row['pk']}")
        restocks = StockMovement.objects.filter(balance_id=OuterRef("balance_id"), order_line_id=OuterRef("order_line_id"), kind="restock").values("balance_id", "order_line_id").annotate(total=Sum("quantity_delta")).values("total")
        for row in StockReservation.objects.annotate(expected_restock=Coalesce(Subquery(restocks), 0)).values("pk", "order_line__offer_id", "balance__offer_id", "status", "order_line__delivery__order__status", "restocked_quantity", "expected_restock").iterator(chunk_size=500):
            expected_order_status = {"reserved": ("pending_payment",), "consumed": ("paid",), "released": ("expired", "cancelled")}
            if row["order_line__offer_id"] != row["balance__offer_id"] or row["order_line__delivery__order__status"] not in expected_order_status.get(row["status"], ()):
                issue("warehouse_allocation_state_mismatch", f"reservation:{row['pk']}")
            if row["restocked_quantity"] != row["expected_restock"]:
                issue("warehouse_restock_history_mismatch", f"reservation:{row['pk']}")
        for order in Order.objects.only("id", "item_total_toman", "shipping_total_toman", "discount_total_toman", "tax_total_toman", "grand_total_toman", "status").prefetch_related("deliveries__lines").iterator(chunk_size=200):
            deliveries = list(order.deliveries.all())
            lines = [line for delivery in deliveries for line in delivery.lines.all()]
            subtotal = sum(line.line_total_toman for line in lines)
            discount = sum(line.discount_toman for line in lines)
            tax = sum(line.tax_toman for line in lines)
            if any(line.tax_toman != (line.line_total_toman-line.discount_toman)*line.tax_rate_bps//10000 for line in lines):
                issue("order_line_tax_mismatch", f"order:{order.pk}")
            shipping = sum(delivery.shipping_fee_toman for delivery in deliveries)
            if (subtotal, discount, shipping, tax, subtotal + shipping - discount + tax) != (order.item_total_toman, order.discount_total_toman, order.shipping_total_toman, order.tax_total_toman, order.grand_total_toman):
                issue("order_snapshot_total_mismatch", f"order:{order.pk}")
            if any(line.unit_price_toman * line.quantity != line.line_total_toman for line in lines):
                issue("order_line_total_mismatch", f"order:{order.pk}")
        from commerce.taxes import unit_amount
        for row in ReturnLine.objects.select_related("order_line").iterator(chunk_size=500):
            positions = row.unit_positions
            valid = (isinstance(positions, list) and len(positions) == row.quantity
                     and all(type(position) is int and 0 <= position < row.order_line.quantity for position in positions)
                     and len(set(positions)) == len(positions))
            if valid:
                expected_tax = unit_amount(row.order_line.tax_toman, row.order_line.quantity, positions)
                expected_net = unit_amount(row.order_line.line_total_toman-row.order_line.discount_toman, row.order_line.quantity, positions)
                if row.tax_amount_toman != expected_tax or row.amount_toman != expected_net+expected_tax:
                    issue("return_component_mismatch", f"return-line:{row.pk}")
            elif row.order_line.tax_toman or row.tax_amount_toman:
                issue("tax_return_allocation_missing", f"return-line:{row.pk}")
        # Independent aggregates avoid multiplying captures and refunds by joins.
        cash = LedgerEntry.objects.filter(attempt_id=OuterRef("pk"))
        captures = cash.filter(kind="payment_capture").values("attempt_id").annotate(total=Sum("amount_toman")).values("total")
        refunds = cash.filter(kind="payment_refund").values("attempt_id").annotate(total=Sum("amount_toman")).values("total")
        for attempt in PaymentAttempt.objects.annotate(captured=Coalesce(Subquery(captures), 0), refunded=Coalesce(Subquery(refunds), 0)).values("id", "status", "amount_toman", "captured", "refunded").iterator(chunk_size=500):
            if attempt["refunded"] > 0 or -attempt["refunded"] > attempt["captured"]:
                issue("refund_exceeds_capture", f"attempt:{attempt['id']}")
            if attempt["status"] == "captured" and attempt["captured"] != attempt["amount_toman"]:
                issue("capture_amount_mismatch", f"attempt:{attempt['id']}")
            if attempt["status"] in ("captured", "review_required") and attempt["captured"] <= 0:
                issue("capture_missing", f"attempt:{attempt['id']}")
        bad_cash = LedgerEntry.objects.filter(kind__in=["payment_capture", "payment_refund"]).filter(Q(attempt__isnull=True) | ~Q(order_id=F("attempt__order_id")) | Q(kind="payment_capture", amount_toman__lte=0) | Q(kind="payment_refund", amount_toman__gte=0))
        for pk in bad_cash.values_list("pk", flat=True).iterator(chunk_size=500):
            issue("cash_ledger_invalid", f"ledger:{pk}")
        accepted_cash = LedgerEntry.objects.filter(order_id=OuterRef("pk"), kind="payment_capture", attempt__status="captured").values("order_id").annotate(total=Sum("amount_toman")).values("total")
        for row in Order.objects.filter(status="paid").annotate(accepted_cash=Coalesce(Subquery(accepted_cash), 0)).values("pk", "grand_total_toman", "accepted_cash").iterator(chunk_size=500):
            if row["accepted_cash"] <= 0:
                issue("paid_order_without_capture", f"order:{row['pk']}")
            elif row["accepted_cash"] != row["grand_total_toman"]:
                issue("paid_order_capture_mismatch", f"order:{row['pk']}")
        report = {"generated_at": timezone.now().isoformat(), "database_vendor": connection.vendor, "snapshot": "repeatable_read" if connection.vendor == "postgresql" and not outer_transaction else "caller_transaction" if outer_transaction else "sqlite_transaction", "consistent": issue_count == 0, "issue_count": issue_count, "issues": issues, "issues_truncated": issue_count > len(issues), "counts": {"orders": Order.objects.count(), "offers": Offer.objects.count(), "payment_attempts": PaymentAttempt.objects.count(), "ledger_entries": LedgerEntry.objects.count(), "review_required_payments": PaymentAttempt.objects.filter(status="review_required").count()}, "cash_totals_toman": {"captured": LedgerEntry.objects.filter(kind="payment_capture").aggregate(total=Sum("amount_toman"))["total"] or 0, "refunded": -(LedgerEntry.objects.filter(kind="payment_refund").aggregate(total=Sum("amount_toman"))["total"] or 0)}, "scope": "Structural snapshot checks only; not provider/bank reconciliation, accounting certification, backup completeness or launch acceptance."}
    return report
