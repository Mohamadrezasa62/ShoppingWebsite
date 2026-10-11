from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Sum
from catalog.models import Offer
from catalog.inventory import InventoryError, restock_line
from payments.models import PaymentAttempt
from payments.orchestration import sandbox_enabled
from payments.services import record_verified_refund
from operations.events import emit
from .models import Order, OrderDelivery, OrderLine, ReturnCase, ReturnLine
from .services import CheckoutError
from .taxes import unit_amount


def create_line_return(user, delivery_id, line_id, quantity, reason):
    if type(quantity) is not int or not 1 <= quantity <= 100 or not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 2000:
        raise CheckoutError("invalid_return", 400)
    with transaction.atomic():
        account = get_user_model().objects.select_for_update().get(pk=user.pk)
        if not account.is_active:
            raise CheckoutError("account_unavailable", 403)
        reference = OrderDelivery.objects.filter(pk=delivery_id, order__user=user).values_list("order_id", flat=True).first()
        if reference is None:
            raise CheckoutError("delivery_not_found", 404)
        order = Order.objects.select_for_update().get(pk=reference)
        delivery = OrderDelivery.objects.select_for_update().get(pk=delivery_id)
        if order.status != Order.Status.PAID or delivery.status != OrderDelivery.Status.DELIVERED:
            raise CheckoutError("return_not_eligible")
        line = OrderLine.objects.filter(pk=line_id, delivery=delivery).first()
        if line is None:
            raise CheckoutError("line_not_found", 404)
        if ReturnCase.objects.filter(delivery=delivery).exclude(status="rejected").filter(lines__isnull=True).exists():
            raise CheckoutError("legacy_return_requires_review")
        previous_lines = list(ReturnLine.objects.filter(order_line=line).exclude(case__status="rejected"))
        if any(len(row.unit_positions) != row.quantity for row in previous_lines):
            raise CheckoutError("legacy_return_requires_review")
        occupied = {position for row in previous_lines for position in row.unit_positions}
        positions = [position for position in range(line.quantity) if position not in occupied][:quantity]
        if len(positions) != quantity:
            raise CheckoutError("return_quantity_exceeded")
        net_paid = line.line_total_toman - line.discount_toman
        tax_amount = unit_amount(line.tax_toman, line.quantity, positions)
        amount = unit_amount(net_paid, line.quantity, positions) + tax_amount
        case = ReturnCase.objects.create(delivery=delivery, requested_by=user, reason=reason.strip(), requested_amount_toman=amount)
        ReturnLine.objects.create(case=case, order_line=line, quantity=quantity, amount_toman=amount, tax_amount_toman=tax_amount, unit_positions=positions)
        emit(f"return:{case.pk}:requested", "return.requested", order_id=order.pk, return_id=case.pk)
        return case


def transition_return(case_id, desired, restock=False):
    allowed = {"requested": {"approved", "rejected"}, "approved": {"received"}, "received": {"refund_pending"}}
    with transaction.atomic():
        reference = ReturnCase.objects.values_list("delivery__order_id", flat=True).get(pk=case_id)
        order = Order.objects.select_for_update().get(pk=reference)
        case = ReturnCase.objects.select_for_update().get(pk=case_id)
        if desired not in allowed.get(case.status, set()):
            raise CheckoutError("invalid_return_transition")
        if desired == "received" and restock:
            lines = list(case.lines.select_related("order_line"))
            if not lines:
                raise CheckoutError("legacy_return_requires_review")
            offers = {row.pk: row for row in Offer.objects.select_for_update().filter(pk__in=[row.order_line.offer_id for row in lines]).order_by("pk")}
            for row in lines:
                offer = offers[row.order_line.offer_id]
                try:
                    restock_line(offer, row.order_line, row.unit_positions, f"return-line:{row.pk}:restock")
                except InventoryError as error:
                    raise CheckoutError(error.code)
        case.status = desired
        case.save(update_fields=["status", "updated_at"])
        emit(f"return:{case.pk}:{desired}", "return.updated", order_id=order.pk, return_id=case.pk, status=desired)
        return case


def refund_sandbox_return(case_id):
    if not sandbox_enabled():
        raise CheckoutError("provider_unavailable", 503)
    with transaction.atomic():
        reference = ReturnCase.objects.values_list("delivery__order_id", flat=True).get(pk=case_id)
        order = Order.objects.select_for_update().get(pk=reference)
        case = ReturnCase.objects.select_for_update().get(pk=case_id)
        if case.status == "refunded":
            return case
        if case.status not in ("received", "refund_pending") or not case.lines.exists():
            raise CheckoutError("return_not_refundable")
        attempt = PaymentAttempt.objects.filter(order=order, provider="sandbox", status="captured").first()
        if attempt is None:
            raise CheckoutError("sandbox_capture_required")
        if case.requested_amount_toman:
            record_verified_refund(attempt.pk, f"sandbox-return-{case.pk}", case.requested_amount_toman)
        from payments.finance import reverse_return_payable
        reverse_return_payable(case)
        case.status = "refunded"
        case.save(update_fields=["status", "updated_at"])
        emit(f"return:{case.pk}:refunded", "return.refunded", order_id=order.pk, return_id=case.pk)
        return case
