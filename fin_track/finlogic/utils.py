from pathlib import Path
from django.core.mail import send_mail
from .models import FileIntegrity
from django.utils.timezone import now
from django.conf import settings
from celery import shared_task
from smtplib import SMTPException

@shared_task(bind=True, max_retries=5)
def send_mail_task(self, title, msg):
    try:
        send_mail(title, msg, settings.SENDER_EMAIL, settings.TARGETS_EMAIL)
    except SMTPException as exc:
        raise self.retry(exc=exc, countdown=60)


def get_file_csv():
    path_dummy_data = Path("/data/data/com.termux/files/home/dummy-data")

    # Jika direktori kosong
    if not any(path_dummy_data.iterdir()):
        message = (
            f"Sistem tidak menemukan file di lokasi berikut:\n"
            f"{path_dummy_data}\n\n"
            f"Silakan periksa apakah file sudah diunggah atau dipindahkan dengan benar.\n\n"
            f"Sistem Monitoring File"
        )
        send_mail_task.delay("Tidak Ada File di Direktori", message)
        return

    last_file = FileIntegrity.objects.last()

    if last_file and last_file.last_checked.date() != now().date() and now().hour >= 8:
        # ambil file baru
        number = int(last_file.filename.split("_")[1].split(".")[0])
        file_name = f"data_{number + 1}.csv"
        new_file = True
    else:
        file_name = getattr(last_file, "filename", "data_1.csv")
        new_file = False

    # cek apakah file_name ada di direktori
    match = next((item for item in path_dummy_data.iterdir() if item.is_file() and item.name == file_name), None)
    
    if match:
        return {
            "is_new_file": new_file,
            "file_name": file_name,
            "file": match
        }
    else:
        message = (
            f"Sistem tidak menemukan file {file_name} di lokasi berikut:\n"
            f"{path_dummy_data}\n\n"
            f"Silakan periksa apakah file sudah diunggah atau dipindahkan dengan benar.\n\n"
            f"Sistem Monitoring File"
        )
        send_mail_task.delay("File Tidak Ditemukan di Direktori", message)
        return
    
    
        
