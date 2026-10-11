from uuid import UUID
from django.db import transaction
from django.utils import timezone
from commerce.models import Order, OrderDelivery, ReturnCase
from operations.models import OrderDispute
from operations.disputes import OPEN_DISPUTES
from sellers.models import Seller
from .finance import accrue_delivery
from .models import LedgerEntry, PaymentAttempt, Settlement, SettlementLine
from .orchestration import PaymentError, sandbox_enabled


def prepare_settlement(actor, seller_id, request_key):
    try:
        key = UUID(str(request_key))
    except (ValueError, TypeError, AttributeError):
        raise PaymentError("invalid_idempotency_key", 400)
    with transaction.atomic():
        seller = Seller.objects.select_for_update().get(pk=seller_id)
        if existing := Settlement.objects.filter(seller=seller, idempotency_key=key).first():
            return existing
        for delivery_id in OrderDelivery.objects.filter(seller=seller, status="delivered", order__status="paid").values_list("pk", flat=True):
            accrue_delivery(delivery_id)
        held_orders = ReturnCase.objects.filter(delivery__seller=seller).exclude(status__in=("rejected", "refunded")).values("delivery__order_id")
        disputed_orders = OrderDispute.objects.filter(delivery__seller=seller, status__in=OPEN_DISPUTES).values("delivery__order_id")
        entries = list(LedgerEntry.objects.select_for_update(of=("self",)).filter(seller=seller, kind="seller_payable", settlement_line__isnull=True).exclude(order_id__in=held_orders).exclude(order_id__in=disputed_orders).order_by("pk"))
        total = sum(entry.amount_toman for entry in entries)
        if total <= 0:
            raise PaymentError("no_payable_balance")
        settlement = Settlement.objects.create(seller=seller, amount_toman=total, created_by=actor, idempotency_key=key, entry_snapshot=[{"ledger_id": entry.pk, "amount_toman": entry.amount_toman} for entry in entries])
        SettlementLine.objects.bulk_create([SettlementLine(settlement=settlement, ledger_entry=entry) for entry in entries])
        return settlement


def approve_settlement(actor, settlement_id):
    with transaction.atomic():
        settlement = Settlement.objects.select_for_update().get(pk=settlement_id)
        if settlement.created_by_id == actor.pk:
            raise PaymentError("second_approver_required", 403)
        if settlement.status != "draft":
            if settlement.status in ("approved", "simulated_paid"):
                return settlement
            raise PaymentError("settlement_not_approvable")
        settlement.status = "approved"
        settlement.approved_by = actor
        settlement.save(update_fields=["status", "approved_by"])
        return settlement


def simulate_payout(settlement_id):
    if not sandbox_enabled():
        raise PaymentError("provider_unavailable", 503)
    with transaction.atomic():
        seller_id = Settlement.objects.values_list("seller_id", flat=True).get(pk=settlement_id)
        Seller.objects.select_for_update().get(pk=seller_id)
        settlement = Settlement.objects.select_for_update().get(pk=settlement_id)
        if settlement.status == "simulated_paid":
            return settlement
        if settlement.status != "approved":
            raise PaymentError("settlement_not_approved")
        order_ids = list(settlement.lines.values_list("ledger_entry__order_id", flat=True))
        list(Order.objects.select_for_update().filter(pk__in=order_ids).order_by("pk").values_list("pk", flat=True))
        if OrderDispute.objects.filter(delivery__order_id__in=order_ids, delivery__seller_id=seller_id, status__in=OPEN_DISPUTES).exists():
            raise PaymentError("settlement_has_open_disputes")
        captured_orders = set(PaymentAttempt.objects.filter(order_id__in=order_ids, status="captured", provider="sandbox").values_list("order_id", flat=True))
        if captured_orders != set(order_ids):
            raise PaymentError("sandbox_capture_required")
        if PaymentAttempt.objects.filter(order_id__in=order_ids, status="captured").exclude(provider="sandbox").exists():
            raise PaymentError("real_payment_cannot_be_simulated")
        if ReturnCase.objects.filter(delivery__order_id__in=order_ids).exclude(status__in=("rejected", "refunded")).exists():
            raise PaymentError("settlement_has_open_returns")
        # A refund after preparation requires a new calculation, never paying
        # the old gross amount. Block this settlement until manually resolved.
        if LedgerEntry.objects.filter(seller=settlement.seller, kind="seller_payable", amount_toman__lt=0, settlement_line__isnull=True, order_id__in=order_ids).exists():
            raise PaymentError("settlement_requires_recalculation")
        settlement.status = "simulated_paid"
        settlement.paid_at = timezone.now()
        settlement.save(update_fields=["status", "paid_at"])
        return settlement


def cancel_settlement(settlement_id):
    with transaction.atomic():
        seller_id = Settlement.objects.values_list("seller_id", flat=True).get(pk=settlement_id)
        Seller.objects.select_for_update().get(pk=seller_id)
        settlement = Settlement.objects.select_for_update().get(pk=settlement_id)
        if settlement.status == "cancelled":
            return settlement
        if settlement.status not in ("draft", "approved"):
            raise PaymentError("settlement_not_cancellable")
        settlement.lines.all().delete()
        settlement.status = "cancelled"
        settlement.save(update_fields=["status"])
        return settlement
