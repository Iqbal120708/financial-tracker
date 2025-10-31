import os

from celery import Celery

# Atur default settings Django untuk Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fin_track.settings")

app = Celery("fin_track")

# Baca konfigurasi dari settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Temukan task secara otomatis di apps
app.autodiscover_tasks()
