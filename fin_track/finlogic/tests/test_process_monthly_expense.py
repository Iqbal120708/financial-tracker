from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
from finlogic.file_processors import ProcessFile
from finlogic.tests.helper_test import generate_dummy_file_monthly_expense
import tempfile
from django.conf import settings
import json
import gspread
import csv
from finlogic.models import FileIntegrity


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SENDER_EMAIL="system@example.com",
    TARGETS_EMAIL=["target@example.com"],
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
@patch("finlogic.file_processors.logger")
class TestWorksheet(TestCase):
    # @patch("finlogic.file_processors.hashlib.sha256")
    def test_success(self, mock_logger):
        # generate_fake_hash(mock_sha256)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file_monthly_expense(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # value palsu google sheets
                # tanpa data hanya header
                fake_ws.get_all_values.return_value = [
                    ["month", "total_expense", "avg_per_day", "days_count"],
                    ["2025-09", 120000, 6000, 20],
                ]

                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_monthly_expense()
                    )

                # yang masuk rows_for_update adalah month 2025-09
                self.assertEqual(
                    rows_for_update,
                    [
                        {
                            # nilai awal dari google sheets 120000
                            # ditambah 5000 dari dummy_file
                            # days_count nambah 1 hari karena dummy_file
                            # rata rata hasil variabel avg_combined
                            "range": "B2:D2",
                            "values": [[125000, 5952, 21]],
                        }
                    ],
                )

                # yang masuk rows_for_append adalah month 2025-10
                self.assertEqual(rows_for_append, [["2025-10", 10000, 10000, 1]])

                mock_logger.info.assert_any_call(
                    "Memulai pemrosesan file sheets bagian Pengeluaran Bulanan"
                )
                mock_logger.info.assert_any_call(
                    "Data bagian yang di update berhasil di upload"
                )
                mock_logger.info.assert_any_call(
                    "Data bagian yang di add berhasil di upload"
                )

    def test_reprocess_file_with_new_data_added(self, mock_logger):
        """
        File hasil process di-process ulang dengan nambah data baru
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file_monthly_expense(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # value palsu google sheets
                # tanpa data hanya header
                get_all_values_default = [
                    ["month", "total_expense", "avg_per_day", "days_count"],
                    ["2025-09", 120000, 6000, 20],
                ]
                fake_ws.get_all_values.return_value = get_all_values_default

                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_monthly_expense()
                    )
                    obj.change_data_model()

                model = FileIntegrity.objects.first()
                self.assertEqual(
                    model.latest_monthly_expense_data,
                    {
                        "2025-09": {
                            "total_new": 5000, "days_count_new": 1
                        },
                        "2025-10": {
                            "total_new": 10000, "days_count_new": 1
                        }
                    }
                )
                
                # ubah values berdasarkan baris agar data sheets berubah sesuai update
                for item in rows_for_update:
                    index = int(item["range"][1]) - 1
                    # index 1 > total_expense, 2 > avg_per_day, 3 > days_count
                    get_all_values_default[index][1] = item["values"][0][0]
                    get_all_values_default[index][2] = item["values"][0][1]
                    get_all_values_default[index][3] = item["values"][0][2]

                # tambah data berdasarkan baris agar data sheets berubah sesuai yang terbaru
                for item in rows_for_append:
                    get_all_values_default.append(item)

                fake_ws.get_all_values.return_value = get_all_values_default

                # tambah data baru (simulasi file berubah)
                with dummy_file.open("a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["2025-10-25", "Transportasi", "Tiket Umum", 5000])

                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_monthly_expense()
                    )
                    obj.change_data_model()

                self.assertEqual(
                    rows_for_update,
                    [
                        # nilai awal dari google sheets 120000
                        # ditambah 5000 dari dummy_file
                        # days_count nambah 1 hari karena dummy_file
                        # rata rata hasil variabel avg_combined
                        {"range": "B2:D2", "values": [[125000, 5952, 21]]},
                        # ini adalah baris 2025-10 nilai ini nambah 5000 karena menambah data baru di file csv sehingga days_count juga bertambah 1
                        {"range": "B3:D3", "values": [[15000, 7500, 2]]},
                    ],
                )

                # yang masuk rows_for_append adalah month 2025-10
                self.assertEqual(rows_for_append, [])
                
                model.refresh_from_db()
                self.assertEqual(
                    model.latest_monthly_expense_data,
                    {
                        "2025-09": {
                            "total_new": 5000, "days_count_new": 1
                        },
                        "2025-10": {
                            "total_new": 15000, "days_count_new": 2
                        }
                    }
                )
                
    def test_reprocess_file_with_price_updated(self, mock_logger):
        """
        File hasil process di-process ulang dengan update harga salah satu data
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file_monthly_expense(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # value palsu google sheets
                # tanpa data hanya header
                get_all_values_default = [
                    ["month", "total_expense", "avg_per_day", "days_count"],
                    ["2025-09", 120000, 6000, 20],
                ]
                fake_ws.get_all_values.return_value = get_all_values_default

                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_monthly_expense()
                    )
                    obj.change_data_model()
                    
                model = FileIntegrity.objects.first()
                self.assertEqual(
                    model.latest_monthly_expense_data,
                    {
                        "2025-09": {
                            "total_new": 5000, "days_count_new": 1
                        },
                        "2025-10": {
                            "total_new": 10000, "days_count_new": 1
                        }
                    }
                )
                

                # ubah values berdasarkan baris agar data sheets berubah sesuai update
                for item in rows_for_update:
                    index = int(item["range"][1]) - 1
                    # index 1 > total_expense, 2 > avg_per_day, 3 > days_count
                    get_all_values_default[index][1] = item["values"][0][0]
                    get_all_values_default[index][2] = item["values"][0][1]
                    get_all_values_default[index][3] = item["values"][0][2]

                # tambah data berdasarkan baris agar data sheets berubah sesuai yang terbaru
                for item in rows_for_append:
                    get_all_values_default.append(item)

                fake_ws.get_all_values.return_value = get_all_values_default

                # update data (simulasi file berubah)
                with dummy_file.open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "category", "subcategory", "price"])
                    writer.writerow(
                        ["2025-09-21", "Makanan & Minuman", "Cemilan", 5000]
                    )
                    writer.writerow(["2025-10-24", "Transportasi", "Tiket Umum", 20000])

                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_monthly_expense()
                    )
                    obj.change_data_model()

                self.assertEqual(
                    rows_for_update,
                    [
                        # nilai awal dari google sheets 120000
                        # ditambah 5000 dari dummy_file
                        # days_count nambah 1 hari karena dummy_file
                        # rata rata hasil variabel avg_combined
                        {"range": "B2:D2", "values": [[125000, 5952, 21]]},
                        # ini adalah baris 2025-10 nilai ini diubah jadi 20000
                        {"range": "B3:D3", "values": [[20000, 20000, 1]]},
                    ],
                )

                # yang masuk rows_for_append adalah month 2025-10
                self.assertEqual(rows_for_append, [])
                
                model.refresh_from_db()
                self.assertEqual(
                    model.latest_monthly_expense_data,
                    {
                        "2025-09": {
                            "total_new": 5000, "days_count_new": 1
                        },
                        "2025-10": {
                            "total_new": 20000, "days_count_new": 1
                        }
                    }
                )
                
                
    def test_reprocess_file_with_month_updated(self, mock_logger):
        """
        File hasil process di-process ulang dengan update month salah satu data
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file_monthly_expense(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # value palsu google sheets
                # tanpa data hanya header
                get_all_values_default = [
                    ["month", "total_expense", "avg_per_day", "days_count"],
                    ["2025-09", 120000, 6000, 20],
                ]
                fake_ws.get_all_values.return_value = get_all_values_default

                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_monthly_expense()
                    )
                    obj.change_data_model()
                
                model = FileIntegrity.objects.first()
                self.assertEqual(
                    model.latest_monthly_expense_data,
                    {
                        "2025-09": {
                            "total_new": 5000, "days_count_new": 1
                        },
                        "2025-10": {
                            "total_new": 10000, "days_count_new": 1
                        }
                    }
                )
                
                # ubah values berdasarkan baris agar data sheets berubah sesuai update
                for item in rows_for_update:
                    index = int(item["range"][1]) - 1
                    # index 1 > total_expense, 2 > avg_per_day, 3 > days_count
                    get_all_values_default[index][1] = item["values"][0][0]
                    get_all_values_default[index][2] = item["values"][0][1]
                    get_all_values_default[index][3] = item["values"][0][2]

                # tambah data berdasarkan baris agar data sheets berubah sesuai yang terbaru
                for item in rows_for_append:
                    get_all_values_default.append(item)

                fake_ws.get_all_values.return_value = get_all_values_default

                # update data (simulasi file berubah)
                with dummy_file.open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "category", "subcategory", "price"])
                    writer.writerow(
                        ["2025-09-21", "Makanan & Minuman", "Cemilan", 5000]
                    )
                    writer.writerow(["2025-09-24", "Transportasi", "Tiket Umum", 10000])

                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_monthly_expense()
                    )
                    obj.change_data_model()
                    
                self.assertEqual(
                    rows_for_update,
                    [
                        # nilai awal dari google sheets 120000
                        # ditambah 5000 dari dummy_file
                        # days_count nambah 1 hari karena dummy_file
                        # rata rata hasil variabel avg_combined
                        # karena update ubah month jadi 2025-09 maka di tambah 10000 lagi dan days_count juga di tambah 1
                        {"range": "B2:D2", "values": [[135000, 6136, 22]]},
                        # ini adalah baris 2025-10 nilai ini tadinya 10000
                        # karena update ubah month jadi 2025-09 maka di kurangi 10000 lagi dan days_count juga di kurangi 1 sehingga nilai 0
                        # atau juga karena file csv tak ada data yang memiliki month 2025-10 maka nilai ini 0 semua
                        {"range": "B3:D3", "values": [[0, 0, 0]]},
                    ],
                )

                # yang masuk rows_for_append adalah month 2025-10
                self.assertEqual(rows_for_append, [])

                model.refresh_from_db()
                self.assertEqual(
                    model.latest_monthly_expense_data,
                    {
                        "2025-09": {
                            "total_new": 15000, "days_count_new": 2
                        },
                    }
                )
                