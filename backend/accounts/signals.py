from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def record_session_version(sender, request, user, **kwargs):
    request.session["account_session_version"] = user.session_version
