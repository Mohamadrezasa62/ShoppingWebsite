from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .roles import STAFF_ROLES, staff_role_required


@require_GET
@staff_role_required(*STAFF_ROLES)
def overview(_request):
    return JsonResponse({"status": "ready", "area": "admin"})


@require_GET
@staff_role_required("finance_operator", "system_administrator")
def finance_overview(_request):
    return JsonResponse({"status": "ready", "area": "finance"})
