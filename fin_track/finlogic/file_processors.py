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

        try:
            self.creds = Credentials.from_service_account_file(
                settings.PATH_CREDENTIALS, scopes=self.scopes
            )
        except FileNotFoundError:
            logger.error(
                f"File credentials tidak ditemukan di path: {settings.PATH_CREDENTIALS}"
            )
            raise
        except Exception as e:
            logger.exception(f"Kredensial tidak valid: {e}")
            raise

        try:
            self.gc = gspread.authorize(self.creds)
        except Exception as e:
            logger.exception(f"Gagal menghubungkan ke Google Sheets API: {e}")
            raise

        try:
            self.sh = self.gc.open_by_key(settings.ID_FILE_GOOGLE_SHEETS)
        except gspread.exceptions.SpreadsheetNotFound as e:
            logger.error(
                f"Tidak dapat menemukan spreadsheet dengan ID: {settings.ID_FILE_GOOGLE_SHEETS}"
            )
            raise

        self.file = file
        self.path_data = Path("/data/data/com.termux/files/home/dummy-data")

    def check_changes_data_file(self):
        # cek apakah file lama ada perubahan data
        # data berubah = True

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
            return True

        # ambil data di db untuk membandingkan hashing sekarang dengan yang lama
        try:
            self.last_file = FileIntegrity.objects.get(filename=self.file["file_name"])
        except FileIntegrity.DoesNotExist as e:
            logger.error(
                f"File dengan nama {self.file["file_name"]} tidak ditemukan di database"
            )
            raise

        if self.file_hash == self.last_file.hash_data:
            logger.info(
                "Hash data lama sama dengan hash data baru. Data file tidak berubah"
            )
            message = (
                f"Sistem tidak mendeteksi perubahan pada file {self.file['file_name']} di lokasi berikut:\n"
                f"{self.path_data}\n\n"
                f"Silakan tambah atau buat perubahan pada data file jika di perlukan.\n\n"
                f"Sistem Monitoring File"
            )
            send_mail_task.delay("Data File Tidak Berubah", message)
            return False

        logger.info("Data file berubah")
        return True

    def group_file_data(self):
        with self.file["file"].open("r", encoding="utf-8") as f:
            logger.info("Melakukan pengambilan dan pengelompokkan data file")

            reader = csv.DictReader(f)
            # buat variabel untuk tempat hasil grouping data
            self.grouped_data_category = {}
            self.grouped_monthly_data = {}

            for i, row in enumerate(reader):
                # mengecek baris data jika ada field yang kosonk maka data akan diskip dan ke baris selanjutnya
                missing_fields = [key for key, value in row.items() if not value]
                if missing_fields:
                    logger.warning(
                        f"Baris {i + 1}: Data kosong pada field {', '.join(missing_fields)} di file {self.file['file_name']}"
                    )
                    continue

                # tambah key baru
                # "2025-11-08" => "2025-11"
                row["month"] = "-".join(row["date"].split("-")[:2])

                date = row.get("date")
                category = row.get("category")
                price = int(row.get("price"))
                month = row.get("month")

                self.grouped_data_category.setdefault(month, {}).setdefault(
                    category, []
                ).append(price)

                self.grouped_monthly_data.setdefault(month, {}).setdefault(
                    date, []
                ).append(price)

            logger.info(
                f"Pengelompokan data dari file {self.file['file_name']} telah selesai diproses"
            )
            return self.grouped_data_category, self.grouped_monthly_data

    def get_worksheet(self, name):
        try:
            worksheet = self.sh.worksheet(name)
            self.values = worksheet.get_all_values()
            header = self.values[0]

            if (
                header != ["month", "category", "total_expense"]
                and name == "Pengeluaran Category"
            ):
                raise Exception(
                    "Header tidak sesuai untuk worksheet 'Pengeluaran Category'"
                )

            elif (
                header != ["month", "total_expense", "avg_per_day", "days_count"]
                and name == "Pengeluaran Bulanan"
            ):
                raise Exception(
                    "Header tidak sesuai untuk worksheet 'Pengeluaran Bulanan'"
                )

            data_rows = self.values[1:] if len(self.values) > 1 else []
            lookup = {}
            return worksheet, data_rows, lookup

        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Worksheet '{name}' tidak ditemukan.")
            raise

        except Exception as e:
            logger.exception(f"Gagal mengambil worksheet: {e}")
            raise

    def change_sheets(self, worksheet, rows_for_update, rows_for_append):
        try:
            if rows_for_update:
                worksheet.batch_update(rows_for_update)
                logger.info("Data bagian yang di update berhasil di upload")
            if rows_for_append:
                worksheet.append_rows(rows_for_append)
                logger.info("Data bagian yang di add berhasil di upload")
        except gspread.exceptions.APIError as e:
            logger.exception(f"API error saat mengubah sheet: {e}")
            raise
        except Exception as e:
            logger.exception(f"Gagal memperbarui sheet: {e}")
            raise

    def process_file_category_expense(self):
        logger.info("Memulai pemrosesan file sheets bagian Pengeluaran Category")

        worksheet, data_rows, lookup = self.get_worksheet("Pengeluaran Category")

        # mengisi data lookup
        # lookup untuk dapat nyimpan lokasi baris data dan key-nya dibuat agar mudah di ambil pas lagi looping data group
        for i, row in enumerate(data_rows, start=2):  # mulai dari baris ke-2
            month, category = row[0], row[1]
            total_expense = int(row[2])
            lookup[(month, category)] = [i, total_expense]

        # variabel untuk kirim data sesuai format worksheet
        rows_for_update, rows_for_append = [], []

        # untuk nyimpan data hasil pemrosesan file csv di db
        self.latest_category_expense_data = {}

        # mengkelola data hasil grouping agar sesuai format worksheet untuk di upload
        for month, categories_in_month in self.grouped_data_category.items():
            for category, prices in categories_in_month.items():
                key = (month, category)
                total_new = sum(prices)

                self.latest_category_expense_data[f"{month}|{category}"] = total_new

                # ambil data lookup sesuai key (month, category)
                if key in lookup:
                    # ambil baris dan total yang ada di worksheet
                    row_index, total_old = lookup[key]

                    # buat total baru
                    # total_old = total yang ada di get_worksheet
                    # total_new = total dari process file csv
                    new_total = total_old + total_new

                    # simpan lokasi baris yang akan di update dengan data baru
                    rows_for_update.append(
                        {"range": f"C{row_index}", "values": [[new_total]]}
                    )
                else:  # kalo key tak ditemukan berarti data baru
                    rows_for_append.append([month, category, total_new])

        # mengurangi total yang ada di lookup (google sheets) dengan total total hasil dari process category expense
        if not self.file["is_new_file"]:
            for key, total in self.last_file.latest_category_expense_data.items():
                # month|category > (month, category)
                key = tuple(key.split("|"))
                if key in lookup:
                    row_index, total_expense = lookup[key]
                    # ambil baris rows_for_update hasil loop.self.grouped_data_category
                    row = next(
                        (
                            item
                            for item in rows_for_update
                            if item["range"] == f"C{row_index}"
                        ),
                        None,
                    )
                    if row:
                        # jika ada kurangi dengan total dari item latest_category_expense_data
                        row["values"][0][0] -= total
                    else:
                        # jika tidak ada tambah le rows_for_update tapi tapi total_expense di kurangi total
                        # total_expense > nilai dari lookup atau google sheets
                        # total > nilai dari item latest_category_expense_data
                        rows_for_update.append(
                            {
                                "range": f"C{row_index}",
                                "values": [[total_expense - total]],
                            }
                        )

        self.change_sheets(worksheet, rows_for_update, rows_for_append)
        return rows_for_update, rows_for_append

    def process_file_monthly_expense(self):
        logger.info("Memulai pemrosesan file sheets bagian Pengeluaran Bulanan")

        worksheet, data_rows, lookup = self.get_worksheet("Pengeluaran Bulanan")

        # mengisi data lookup
        # lookup untuk dapat nyimpan lokasi baris data dan key-nya dibuat agar mudah di ambil pas lagi looping data group
        for i, row in enumerate(data_rows, start=2):  # mulai dari baris ke-2
            month, total_expense, avg_per_day, days_count = (
                row[0],
                int(row[1]),
                int(row[2]),
                int(row[3]),
            )
            lookup[month] = [i, total_expense, days_count]

        rows_for_update, rows_for_append = [], []

        # untuk nyimpan data hasil pemrosesan file csv di db
        self.latest_monthly_expense_data = {}
        
        for month, dates in self.grouped_monthly_data.items():
            total_new = sum(sum(prices) for prices in dates.values())
            days_count_new = len(dates)
            try:
                avg_new = int(total_new / len(dates))
            except ZeroDivisionError:
                avg_new = 0
                
            self.latest_monthly_expense_data[month] = {
                "total_new": total_new,
                "days_count_new": days_count_new,
            }
            # ambil data lookup sesuai key (month)
            if month in lookup:
                row_index, total_old, days_count_old = lookup[month]
                try:
                    avg_combined = int(
                        (int(total_old) + total_new)
                        / (int(days_count_old) + days_count_new)
                    )
                except ZeroDivisionError:
                    avg_combined = 0
                    
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

        # mengurangi total dan days_count yang ada di lookup (google sheets) dengan total total hasil dari process monthly expense
        if not self.file["is_new_file"]:
            for month, values in self.last_file.latest_monthly_expense_data.items():
                if month in lookup:
                    row_index, total_old, days_count_old = lookup[month]
                    # ambil baris rows_for_update hasil loop.self.grouped_monthly_data
                    row = next(
                        (
                            item
                            for item in rows_for_update
                            if item["range"] == f"B{row_index}:D{row_index}"
                        ),
                        None,
                    )
                    
                    if row:
                        # jika ada kurangi dengan value dari item latest_category_expense_data
                        row["values"][0][0] -= values["total_new"]
                        row["values"][0][2] -= values["days_count_new"]

                        try:
                            row["values"][0][1] = int(
                                row["values"][0][0] / row["values"][0][2]
                            )
                        except ZeroDivisionError:
                            row["values"][0][1] = 0
                    else:
                        # jika tidak ada tambah ke rows_for_update
                        # tapi total_old di kurangi total_new values
                        # days_count_old di kurangi days_count dari values
                        # total_old > nilai dari lookup atau google sheets
                        # total_new > nilai dari item latest_category_expense_data
                        total = total_old - values["total_new"]
                        days_count = days_count_old - values["days_count_new"]
                        try:
                            avg = total / days_count
                        except ZeroDivisionError:
                            avg = 0

                        rows_for_update.append(
                            {
                                "range": f"B{row_index}:D{row_index}",
                                "values": [[total, avg, days_count]],
                            }
                        )

        self.change_sheets(worksheet, rows_for_update, rows_for_append)

        return rows_for_update, rows_for_append

    def change_data_model(self):
        if not self.file["is_new_file"]:
            self.last_file.hash_data = self.file_hash
            self.last_file.last_checked = now()
            self.last_file.latest_category_expense_data = getattr(
                self, "latest_category_expense_data", {}
            )
            self.last_file.latest_monthly_expense_data = getattr(
                self, "latest_monthly_expense_data", {}
            )
            self.last_file.save()
        else:
            FileIntegrity.objects.create(
                filename=self.file["file_name"],
                hash_data=self.file_hash,
                last_checked=now(),
                latest_category_expense_data=getattr(
                    self, "latest_category_expense_data", {}
                ),
                latest_monthly_expense_data=getattr(
                    self, "latest_monthly_expense_data", {}
                ),
            )

    def send_email_success(self):
        message = (
            f"Sistem berhasil melakukan pemrosesan pada file {self.file['file_name']} di lokasi berikut:\n"
            f"{self.path_data}\n\n"
            f"Sistem Monitoring File"
        )
        send_mail_task.delay("Data File Berhasil di Proses", message)
