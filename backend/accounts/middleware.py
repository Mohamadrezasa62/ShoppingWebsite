from django.contrib.auth import logout
from django.http import JsonResponse


class SessionRevocationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.get("account_session_version", 0) != request.user.session_version:
            logout(request)
            if request.path.startswith("/api/"):
                return JsonResponse({"error": "session_revoked"}, status=401)
        return self.get_response(request)
