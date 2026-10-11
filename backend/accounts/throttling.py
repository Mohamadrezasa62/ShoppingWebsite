"""Shared-cache fixed windows; peer IP only, never arbitrary forwarded headers."""
import ipaddress
import time
from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import salted_hmac
from .services import TooManyRequests, AuthenticationUnavailable


LIMITS = {"request": ((600, 20), (3600, 100)), "verify": ((900, 100),)}


def client_identity(request):
    def parse(value):
        address = ipaddress.ip_address(value)
        return getattr(address, "ipv4_mapped", None) or address
    try:
        peer = parse(request.META.get("REMOTE_ADDR", ""))
    except ValueError:
        return "unknown-peer"
    try:
        networks = [ipaddress.ip_network(value, strict=True) for value in settings.AUTH_TRUSTED_PROXY_NETWORKS]
        if any(network.prefixlen == 0 for network in networks):
            raise ValueError()
    except ValueError:
        raise AuthenticationUnavailable() from None
    if any(peer in network for network in networks):
        try:
            return str(parse(request.META.get("HTTP_X_REAL_IP", "")))
        except ValueError:
            return "unknown-proxied-client"
    return str(peer)


def limit_peer(request, operation):
    peer = client_identity(request)
    identity = salted_hmac("shopping.auth.peer", peer, algorithm="sha256").hexdigest()
    now = int(time.time())
    try:
        for seconds, maximum in LIMITS[operation]:
            key = f"auth:peer:{operation}:{identity}:{seconds}:{now//seconds}"
            # A current bucket cannot naturally expire between add and incr.
            cache.add(key, 0, seconds*2)
            if cache.incr(key) > maximum:
                raise TooManyRequests(retry_after=seconds-now%seconds)
    except TooManyRequests:
        raise
    except Exception as error:
        raise AuthenticationUnavailable() from error
