"""Voluntary account deactivation; not legal erasure of retained records."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from commerce.models import Order, ReturnCase, DeliveryCancellation, Cart
from catalog.models import ProductAlert, BrowsingPreference, RecentProductView
from operations.models import AuditEvent, OrderDispute, NotificationPreference
from uuid import uuid4
from .models import AccountClosure


class ClosureError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def protected(user):
    return user.is_staff or user.is_superuser or user.seller_memberships.exists()


def blockers(user):
    return blockers_many([user.pk])[user.pk]


def blockers_many(user_ids):
    result = {pk: [] for pk in user_ids}
    checks = [
        ("pending_payment", Order.objects.filter(user_id__in=user_ids, status="pending_payment").values_list("user_id", flat=True)),
        ("open_delivery", Order.objects.filter(user_id__in=user_ids, status="paid", deliveries__status__in=["awaiting_fulfillment", "packing", "shipped"]).values_list("user_id", flat=True)),
        ("open_return", ReturnCase.objects.filter(requested_by_id__in=user_ids).exclude(status__in=["rejected", "refunded"]).values_list("requested_by_id", flat=True)),
        ("open_cancellation", DeliveryCancellation.objects.filter(requested_by_id__in=user_ids, status__in=["requested", "approved"]).values_list("requested_by_id", flat=True)),
        ("open_dispute", OrderDispute.objects.filter(requested_by_id__in=user_ids, status__in=["open", "seller_responded", "escalated"]).values_list("requested_by_id", flat=True)),
    ]
    for code, rows in checks:
        for pk in rows.distinct():
            result[pk].append(code)
    return result


def audit(actor, case, action, reason, before):
    AuditEvent.objects.create(actor=actor, action=action, target_type="account_closure", target_id=str(case.pk), reason=reason, before={"status": before}, after={"status": case.status})


@transaction.atomic
def request_closure(user, reason):
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if protected(user) or not user.is_active:
        raise ClosureError("protected_account")
    existing = AccountClosure.objects.filter(user=user, status="requested").first()
    if existing:
        if existing.reason != reason:
            raise ClosureError("closure_conflict")
        return existing
    case = AccountClosure.objects.create(user=user, reason=reason)
    audit(user, case, "account_closure_requested", reason, None)
    return case


@transaction.atomic
def withdraw_closure(user, case_id):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    case = AccountClosure.objects.filter(user=user, pk=case_id).first()
    if case is None:
        raise ClosureError("closure_not_found", 404)
    if case.status == "withdrawn":
        return case
    if case.status != "requested":
        raise ClosureError("invalid_closure_transition")
    case.status = "withdrawn"
    case.save(update_fields=["status", "updated_at"])
    audit(user, case, "account_closure_withdrawn", "Customer withdrew request", "requested")
    return case


@transaction.atomic
def decide_closure(case_id, status, actor, reason):
    if status not in ("completed", "rejected"):
        raise ClosureError("invalid_closure_decision", 400)
    reference = AccountClosure.objects.filter(pk=case_id).values_list("user_id", flat=True).first()
    if reference is None:
        raise ClosureError("closure_not_found", 404)
    user = get_user_model().objects.select_for_update().get(pk=reference)
    case = AccountClosure.objects.get(pk=case_id)
    if case.status != "requested":
        raise ClosureError("invalid_closure_transition")
    if status == "completed":
        if protected(user) or not user.is_active or blockers(user):
            raise ClosureError("closure_blocked")
        # Checkout uses the same user-first lock; retained orders/ledger remain intact.
        list(Cart.objects.select_for_update().filter(user=user))
        user.is_active = False
        user.session_version += 1
        user.set_unusable_password()
        user.save(update_fields=["is_active", "session_version", "password"])
        ProductAlert.objects.filter(user=user).update(is_active=False)
        BrowsingPreference.objects.filter(user=user).update(enabled=False, updated_at=timezone.now())
        RecentProductView.objects.filter(user=user).delete()
        NotificationPreference.objects.filter(user=user).update(marketing_in_app=False, revision=uuid4(), updated_at=timezone.now())
    case.status, case.reviewed_by, case.review_note = status, actor, reason
    case.save(update_fields=["status", "reviewed_by", "review_note", "updated_at"])
    audit(actor, case, "account_closure_decided", reason, "requested")
    return case
