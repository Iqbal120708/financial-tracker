from celery import shared_task
from django.core.mail import send_mail
from django.utils.timezone import now
from .utils import get_file_csv
#@shared_task
def check_and_process_file_task():
    get_file_csv()