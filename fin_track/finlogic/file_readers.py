from .utils import send_mail_task
from .models import FileIntegrity
from django.utils.timezone import now
from pathlib import Path


def check_directory(path_dummy_data):
    # Jika direktori kosong
    if not any(path_dummy_data.iterdir()):
        message = (
            f"Sistem tidak menemukan file di lokasi berikut:\n"
            f"{path_dummy_data}\n\n"
            f"Silakan periksa apakah file sudah diunggah atau dipindahkan dengan benar.\n\n"
            f"Sistem Monitoring File"
        )
        send_mail_task.delay("Tidak Ada File di Direktori", message)
        return False

    return True


def get_file_name():
    last_file = FileIntegrity.objects.last()

    if last_file and last_file.last_checked.date() != now().date() and now().hour >= 8:
        # ambil file baru
        number = int(last_file.filename.split("_")[1].split(".")[0])
        file_name = f"data_{number + 1}.csv"
        is_new_file = True
    else:
        file_name = getattr(last_file, "filename", "data_1.csv")
        is_new_file = not hasattr(last_file, "filename")

    return file_name, is_new_file


def find_file(path_dummy_data, file_name):
    # cek apakah file_name ada di direktori
    return next(
        (
            item
            for item in path_dummy_data.iterdir()
            if item.is_file() and item.name == file_name
        ),
        None,
    )


def get_file_csv():
    path_dummy_data = Path("/data/data/com.termux/files/home/dummy-data")

    check_dir = check_directory(path_dummy_data)
    if not check_dir:
        return
    file_name, is_new_file = get_file_name()
    match = find_file(path_dummy_data, file_name)
    if match:
        return {"is_new_file": is_new_file, "file_name": file_name, "file": match}

    message = (
        f"Sistem tidak menemukan file {file_name} di lokasi berikut:\n"
        f"{path_dummy_data}\n\n"
        f"Silakan periksa apakah file sudah diunggah atau dipindahkan dengan benar.\n\n"
        f"Sistem Monitoring File"
    )
    send_mail_task.delay("File Tidak Ditemukan di Direktori", message)
