import json
import logging
import re
import time
from uuid import uuid4

logger = logging.getLogger("marketplace.requests")


class RequestContextMiddleware:
    """Correlate API errors without logging bodies, query strings or credentials."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        request.request_id = supplied if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", supplied) else uuid4().hex
        started = time.monotonic()
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
            logger.info(json.dumps({
                "request_id": request.request_id,
                "method": request.method,
                "route": getattr(request.resolver_match, "route", None),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }))
        return response
