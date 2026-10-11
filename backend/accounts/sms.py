"""Kavenegar verify lookup: bounded HTTPS POST, no retries or provider logging."""
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from django.conf import settings


class DeliveryFailure(Exception):
    pass


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configuration_valid():
    return bool(re.fullmatch(r'[A-Za-z0-9]{16,256}', settings.KAVENEGAR_API_KEY) and
                all(re.fullmatch(r'[A-Za-z0-9_-]{1,100}', name) for name in
                    (settings.KAVENEGAR_LOGIN_TEMPLATE, settings.KAVENEGAR_STAFF_PASSWORD_TEMPLATE)))


def send_otp(phone, code, purpose):
    if not configuration_valid() or not re.fullmatch(r'09[0-9]{9}', phone) or not re.fullmatch(r'[0-9]{6}', code) or purpose not in ('login', 'staff_password'):
        raise DeliveryFailure('SMS configuration/input invalid')
    template = settings.KAVENEGAR_LOGIN_TEMPLATE if purpose == 'login' else settings.KAVENEGAR_STAFF_PASSWORD_TEMPLATE
    request = Request(f'https://api.kavenegar.com/v1/{settings.KAVENEGAR_API_KEY}/verify/lookup.json',
                      data=urlencode({'receptor': phone, 'token': code, 'template': template, 'type': 'sms'}).encode(),
                      headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}, method='POST')
    try:
        with build_opener(RejectRedirect()).open(request, timeout=8) as response:
            if response.status != 200:
                raise ValueError()
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            result = json.loads(raw)
            status = result.get('return', {}).get('status')
            if type(status) is not int or status != 200:
                raise ValueError()
    except Exception:
        # Provider URL includes the API key and response can echo phone/code.
        # Never propagate its exception text, traceback cause or response body.
        raise DeliveryFailure('SMS submission failed') from None
