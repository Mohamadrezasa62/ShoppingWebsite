from celery import shared_task
from .events import drain


@shared_task
def process_outbox():
    return drain()
