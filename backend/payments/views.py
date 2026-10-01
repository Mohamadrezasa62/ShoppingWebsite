from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import PaymentAttempt


@require_GET
def methods(_request):
    return JsonResponse({
        "available": [],
        "planned": [{"id": value, "enabled": False, "reason": "merchant_onboarding_required"} for value in PaymentAttempt.Provider.values],
    })
