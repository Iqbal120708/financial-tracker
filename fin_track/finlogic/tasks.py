from celery import shared_task
from django.core.mail import send_mail
from django.utils.timezone import now
from .file_readers import get_file_csv
from .file_processors import ProcessFile
from .utils import send_mail_task


@shared_task
def check_and_process_file_task():
    file = get_file_csv()

    try:
        obj = ProcessFile(file)
        if obj.check_changes_data_file():
            obj.group_file_data()
            obj.process_file_category_expense()
            obj.process_file_monthly_expense()
            obj.change_data_model()
            obj.send_email_success()
    except Exception as e:
        send_mail_task(
            "Gagal Memproses File CSV",
            f"Terjadi kesalahan saat menjalankan task pengecekan dan pemrosesan file {file['file_name']}. Silakan periksa log untuk detail error.",
        )
