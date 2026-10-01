from typing import Protocol

from .services import VerifiedCapture


class PaymentProvider(Protocol):
    """Contract for a future approved merchant integration."""

    def create_checkout(self, amount_toman: int, callback_url: str, request_key: str) -> str: ...

    def verify_capture(self, provider_reference: str) -> VerifiedCapture: ...

    def refund(self, provider_reference: str, amount_toman: int, request_key: str) -> str: ...

    def reconcile(self, provider_reference: str) -> VerifiedCapture | None: ...
