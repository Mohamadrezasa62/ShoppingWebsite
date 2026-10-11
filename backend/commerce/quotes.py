"""Signed, private quote approval; stock and coupon capacity are not reserved."""
import hashlib
import json
from django.core import signing

QUOTE_MAX_AGE = 600
SALT = "commerce.quote.v1"


class QuoteError(Exception):
    def __init__(self, code):
        self.code = code


def quote_digest(address_snapshot, lines, offers, rules, coupon, discount, delivery_choices=None, delivery_windows=None, taxes=None):
    # Only the digest enters the token; addresses and catalog snapshots remain private.
    payload = {
        "address": address_snapshot,
        "lines": [{
            "id": line.pk, "offer": line.offer_id, "quantity": line.quantity,
            "price": offers[line.offer_id].price_toman,
            "warranty": offers[line.offer_id].warranty,
            "seller": offers[line.offer_id].seller_id,
            "seller_name": offers[line.offer_id].seller.name,
            "commission": offers[line.offer_id].seller.commission_bps,
            "fulfillment": offers[line.offer_id].fulfillment,
            "title": offers[line.offer_id].variant.product.title,
            "attributes": offers[line.offer_id].variant.attributes,
        } for line in lines],
        "shipping": {key: {"id": rule.pk, "fee": rule.fee_toman,
                            "min_days": rule.min_days, "max_days": rule.max_days}
                     for key, rule in rules.items()
                     if key in {offer.fulfillment for offer in offers.values()}},
        "coupon": {"id": coupon.pk, "code": coupon.code} if coupon else None,
        "discount": discount, "currency": "toman",
    }
    if delivery_choices is not None:
        payload["selected_shipping"] = delivery_choices
    if delivery_windows is not None:
        payload["selected_windows"] = delivery_windows
    if taxes is not None:
        payload["taxes"] = taxes
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_quote(user_id, address_id, digest):
    return signing.dumps({"v": 1, "user": user_id, "address": address_id, "digest": digest}, salt=SALT)


def read_quote(token, user_id, address_id, *, replay=False):
    if not isinstance(token, str) or not 1 <= len(token) <= 1024:
        raise QuoteError("invalid_quote")
    try:
        payload = signing.loads(token, salt=SALT, max_age=None if replay else QUOTE_MAX_AGE)
    except signing.SignatureExpired:
        raise QuoteError("quote_expired")
    except (signing.BadSignature, ValueError, TypeError):
        raise QuoteError("invalid_quote")
    if (not isinstance(payload, dict) or payload.get("v") != 1
            or payload.get("user") != user_id or payload.get("address") != address_id
            or not isinstance(payload.get("digest"), str) or len(payload["digest"]) != 64):
        raise QuoteError("invalid_quote")
    return payload["digest"]
