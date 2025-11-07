from django.core.mail import send_mail

from celery import shared_task

from smtplib import SMTPException
from django.conf import settings


@shared_task(bind=True, max_retries=5)
def send_mail_task(self, title, msg):
    try:
        send_mail(title, msg, settings.SENDER_EMAIL, settings.TARGETS_EMAIL)
    except SMTPException as exc:
        raise self.retry(exc=exc, countdown=60)
