from django.http import JsonResponse


STAFF_ROLES = (
    "catalog_operator",
    "support_agent",
    "finance_operator",
    "marketplace_manager",
    "system_administrator",
)


def staff_role_required(*allowed_roles):
    def decorator(view):
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error": "authentication_required"}, status=401)
            if not request.user.is_staff:
                return JsonResponse({"error": "forbidden"}, status=403)
            if not request.user.is_superuser and not request.user.groups.filter(name__in=allowed_roles).exists():
                return JsonResponse({"error": "forbidden"}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
