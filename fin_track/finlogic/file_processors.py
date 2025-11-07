from django.conf import settings
import csv
import hashlib
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from .utils import send_mail_task
from .models import FileIntegrity
from pathlib import Path
from django.utils.timezone import now
import logging

logger = logging.getLogger("fintrack")

# lakukan test
# tambab logging
class ProcessFile:
    def __init__(self, file):
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        self.creds = Credentials.from_service_account_file(
            settings.PATH_CREDENTIALS, scopes=self.scopes
        )
        self.gc = gspread.authorize(self.creds)
        self.sh = self.gc.open_by_key(settings.ID_FILE_GOOGLE_SHEETS)
        self.file = file
        self.path_dummy_data = Path("/data/data/com.termux/files/home/dummy-data")

    def check_changes_data_file(self):
        # cek apakah file lama ada perubahan data
        # nama file ada di model dan data berubah = True
        
        logger.info("Memulai pengecekan data di file")
        
        # membuat hash data file
        hasher = hashlib.sha256()
        with self.file["file"].open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)

        self.file_hash = hasher.hexdigest()
        logger.debug(f"Hash file berhasil dibuat: {self.file_hash}")
        
        if self.file["is_new_file"]:
            logger.info("Menghentikan pengecekan karena file baru")
            return False
        
        # ambil data di db untuk membandingkan hashing sekarang dengan yang lama
        try:
            self.last_file = FileIntegrity.objects.get(
                filename=self.file["file_name"]
            )
        except FileIntegrity.DoesNotExist as e:
            logger.error(f"File dengan nama {self.file["file_name"]} tidak ditemukan di database")
            raise 

        if self.file_hash == self.last_file.hash_data:
            logger.info("Hash data lama sama dengan hash data baru. Data file tidak berubah")
            message = (
                f"Sistem tidak mendeteksi perubahan pada file {self.file['file_name']} di lokasi berikut:\n"
                f"{self.path_dummy_data}\n\n"
                f"Silakan tambah atau buat perubahan pada data file jika di perlukan.\n\n"
                f"Sistem Monitoring File"
            )
            send_mail_task.delay("Data File Tidak Berubah", message)
            return False
        
        logger.info("Data file berubah")
        return True

    def get_file(self):
        with self.file["file"].open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.grouped_data_category = {}
            self.grouped_monthly_data = {}
            for row in reader:
                row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()

                # tambah key baru
                row["month"] = row["date"].strftime("%Y-%m")

                month = row["month"]
                category = row["category"]
                price = int(row["price"])
                date = row["date"]

                self.grouped_data_category.setdefault(month, {}).setdefault(
                    category, []
                ).append(price)

                self.grouped_monthly_data.setdefault(month, {}).setdefault(
                    date, []
                ).append(price)

    def get_worksheet(self, name):
        worksheet = self.sh.worksheet(name)
        values = worksheet.get_all_values()
        data_rows = values[1:]
        lookup = {}
        return worksheet, data_rows, lookup

    def change_sheets(self, worksheet, rows_for_update, rows_for_append):
        if rows_for_update:
            worksheet.batch_update(rows_for_update)
        if rows_for_append:
            worksheet.append_rows(rows_for_append)

    def process_file_category_expense(self):
        worksheet, data_rows, lookup = self.get_worksheet("Pengeluaran Category")
        for i, row in enumerate(data_rows, start=2):  # mulai dari baris ke-2
            month, category = row[0], row[1]
            total_expense = int(row[2])
            lookup[(month, category)] = [i, total_expense]

        rows_for_update, rows_for_append = [], []
        for month, categories_in_month in self.grouped_data_category.items():
            for category, prices in categories_in_month.items():
                key = (month, category)
                total_new = sum(prices)

                if key in lookup:
                    row_index, total_old = lookup[key]
                    new_total = total_old + total_new
                    rows_for_update.append(
                        {"range": f"C{row_index}", "values": [[new_total]]}
                    )
                else:
                    rows_for_append.append([month, category, total_new])

        self.change_sheets(worksheet, rows_for_update, rows_for_append)

    def process_file_monthly_expense(self):
        worksheet, data_rows, lookup = self.get_worksheet("Pengeluaran Bulanan")
        for i, row in enumerate(data_rows, start=2):  # mulai dari baris ke-2
            month, total_expense, avg_per_day, days_count = (
                row[0],
                int(row[1]),
                int(row[2]),
                int(row[3]),
            )
            lookup[month] = [i, total_expense, days_count]

        rows_for_update, rows_for_append = [], []
        for month, dates in self.grouped_monthly_data.items():
            total_new = sum(sum(prices) for prices in dates.values())
            days_count_new = len(dates)
            avg_new = int(total_new / len(dates))

            if month in lookup:
                row_index, total_old, days_count_old = lookup[month]
                avg_combined = int(
                    (int(total_old) + total_new)
                    / (int(days_count_old) + days_count_new)
                )
                rows_for_update.append(
                    {
                        "range": f"B{row_index}:D{row_index}",
                        "values": [
                            [
                                total_new + total_old,
                                avg_combined,
                                days_count_new + days_count_old,
                            ]
                        ],
                    }
                )
            else:
                rows_for_append.append([month, total_new, avg_new, days_count_new])

        self.change_sheets(worksheet, rows_for_update, rows_for_append)

    def change_data_model(self):
        if self.last_file:
            self.last_file.hash_data = self.file_hash
            self.last_file.last_checked = now()
            self.last_file.save()
        else:
            FileIntegrity.objects.create(
                filename=self.file["file_name"],
                hash_data=self.file_hash,
                last_checked=now(),
            )

    def send_email_success(self):
        message = (
            f"Sistem berhasil melakukan pemrosesan pada file {self.file['file_name']} di lokasi berikut:\n"
            f"{self.path_dummy_data}\n\n"
            f"Sistem Monitoring File"
        )
        send_mail_task.delay("Data File Berhasil di Proses", message)
