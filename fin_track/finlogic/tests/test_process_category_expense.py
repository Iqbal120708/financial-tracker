from django.test import TestCase, override_settings
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
from finlogic.file_processors import ProcessFile
from finlogic.tests.helper_test import generate_dummy_file, generate_fake_hash
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
    @patch("finlogic.file_processors.hashlib.sha256")
    def test_success(self, mock_sha256, mock_logger):
        generate_fake_hash(mock_sha256)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # value palsu google sheets
                fake_ws.get_all_values.return_value = [
                    ["month", "category", "total_expense"],
                    ["2025-10", "Makanan & Minuman", 15000],
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
                        obj.process_file_category_expense()
                    )

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file
                self.assertEqual(
                    rows_for_update,
                    [{"range": "C2", "values": [[20000]]}],  # 15000 + 5000
                )

                self.assertEqual(rows_for_append, [["2025-10", "Transportasi", 10000]])

                mock_logger.info.assert_any_call(
                    "Memulai pemrosesan file sheets bagian Pengeluaran Category"
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
        # generate_fake_hash(mock_sha256)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # --- Data di Google Sheet sebelum reprocess ---
                get_all_values_default = [
                    ["month", "category", "total_expense"],
                    ["2025-10", "Makanan & Minuman", 15000],
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
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                model = FileIntegrity.objects.first()
                self.assertEqual(
                    model.latest_category_expense_data,
                    {"2025-10|Makanan & Minuman": 5000, "2025-10|Transportasi": 10000},
                )

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file
                self.assertEqual(
                    rows_for_update,
                    [{"range": "C2", "values": [[20000]]}],  # 15000 + 5000
                )

                self.assertEqual(rows_for_append, [["2025-10", "Transportasi", 10000]])

                # ubah values berdasarkan baris agar data sheets berubah sesuai update
                for item in rows_for_update:
                    index = int(item["range"][1]) - 1
                    get_all_values_default[index][-1] = item["values"][0][0]

                # tambah data berdasarkan baris agar data sheets berubah sesuai yang terbaru
                for item in rows_for_append:
                    get_all_values_default.append(item)

                fake_ws.get_all_values.return_value = get_all_values_default

                # tambah data file csv agar ada perubahan data
                with dummy_file.open("a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(
                        ["2025-10-23", "Hiburan & Gaya Hidup", "Hobi", 75000]
                    )

                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file
                # 10000 data baru Transportasi hasil rows_for_append
                self.assertEqual(
                    rows_for_update,
                    [
                        {"range": "C2", "values": [[20000]]},  # 15000 + 5000
                        {
                            "range": "C3",
                            "values": [[10000]],  # Transportasi
                        },
                    ],
                )

                self.assertEqual(
                    rows_for_append, [["2025-10", "Hiburan & Gaya Hidup", 75000]]
                )

                model.refresh_from_db()
                self.assertEqual(
                    model.latest_category_expense_data,
                    {
                        "2025-10|Makanan & Minuman": 5000,
                        "2025-10|Transportasi": 10000,
                        "2025-10|Hiburan & Gaya Hidup": 75000,
                    },
                )

    def test_reprocess_file_with_price_updated(self, mock_logger):
        """
        File hasil process di-process ulang dengan update harga salah satu data
        """
        # generate_fake_hash(mock_sha256)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:

                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # --- Data di Google Sheet sebelum reprocess ---
                get_all_values_default = [
                    ["month", "category", "total_expense"],
                    ["2025-10", "Makanan & Minuman", 15000],
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
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                model = FileIntegrity.objects.first()
                self.assertEqual(
                    model.latest_category_expense_data,
                    {"2025-10|Makanan & Minuman": 5000, "2025-10|Transportasi": 10000},
                )

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file
                self.assertEqual(
                    rows_for_update,
                    [{"range": "C2", "values": [[20000]]}],  # 15000 + 5000
                )

                self.assertEqual(rows_for_append, [["2025-10", "Transportasi", 10000]])

                # ubah values berdasarkan baris agar data sheets berubah sesuai update
                for item in rows_for_update:
                    index = int(item["range"][1]) - 1
                    get_all_values_default[index][-1] = item["values"][0][0]

                # tambah data berdasarkan baris agar data sheets berubah sesuai yang terbaru
                for item in rows_for_append:
                    get_all_values_default.append(item)

                fake_ws.get_all_values.return_value = get_all_values_default

                # ubah data file csv
                with dummy_file.open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "category", "subcategory", "price"])
                    writer.writerow(
                        ["2025-10-23", "Makanan & Minuman", "Cemilan", 10000]
                    )
                    writer.writerow(["2025-10-23", "Transportasi", "Tiket Umum", 10000])

                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file
                # ubah 5000 jadi 10000
                self.assertEqual(
                    rows_for_update,
                    [
                        {"range": "C2", "values": [[25000]]},  # 15000 + 10000
                        {
                            "range": "C3",
                            "values": [[10000]],  # Transportasi
                        },
                    ],
                )

                self.assertEqual(rows_for_append, [])

                model.refresh_from_db()
                self.assertEqual(
                    model.latest_category_expense_data,
                    {"2025-10|Makanan & Minuman": 10000, "2025-10|Transportasi": 10000},
                )

    def test_reprocess_file_with_category_changed(self, mock_logger):
        """
        File hasil process di-process ulang dengan ubah category salah satu data
        """
        # generate_fake_hash(mock_sha256)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # --- Data di Google Sheet sebelum reprocess ---
                get_all_values_default = [
                    ["month", "category", "total_expense"],
                    ["2025-10", "Makanan & Minuman", 15000],
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
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                model = FileIntegrity.objects.first()
                self.assertEqual(
                    model.latest_category_expense_data,
                    {"2025-10|Makanan & Minuman": 5000, "2025-10|Transportasi": 10000},
                )

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file
                self.assertEqual(
                    rows_for_update,
                    [{"range": "C2", "values": [[20000]]}],  # 15000 + 5000
                )

                self.assertEqual(rows_for_append, [["2025-10", "Transportasi", 10000]])

                # ubah values berdasarkan baris agar data sheets berubah sesuai update
                for item in rows_for_update:
                    index = int(item["range"][1]) - 1
                    get_all_values_default[index][-1] = item["values"][0][0]

                # tambah data berdasarkan baris agar data sheets berubah sesuai yang terbaru
                for item in rows_for_append:
                    get_all_values_default.append(item)

                fake_ws.get_all_values.return_value = get_all_values_default

                # ubah data file csv
                with dummy_file.open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "category", "subcategory", "price"])
                    writer.writerow(["2025-10-23", "Transportasi", "Tiket Umum", 5000])
                    writer.writerow(["2025-10-23", "Transportasi", "Tiket Umum", 10000])

                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file di ubah kategorinya dari makanan > transportasi
                self.assertEqual(
                    rows_for_update,
                    [
                        # karena kategori berubah dan kategori nya sama maka dari 10000 (nilai lama) ditambah 5000 (nilai dari perubahan kategori)
                        {
                            "range": "C3",
                            "values": [[15000]],  # Transportasi
                        },
                        {
                            # range makanan -5000 karena kategorinya di ubah
                            "range": "C2",
                            "values": [[15000]],  # 15000 - 5000
                        },
                    ],
                )

                self.assertEqual(rows_for_append, [])

                model.refresh_from_db()
                self.assertEqual(
                    model.latest_category_expense_data, {"2025-10|Transportasi": 15000}
                )

    def test_reprocess_file_with_month_updated(self, mock_logger):
        """
        File hasil process di-process ulang dengan update month salah satu data
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # --- Data di Google Sheet sebelum reprocess ---
                get_all_values_default = [
                    ["month", "category", "total_expense"],
                    ["2025-10", "Makanan & Minuman", 15000],
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
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                model = FileIntegrity.objects.first()
                self.assertEqual(
                    model.latest_category_expense_data,
                    {"2025-10|Makanan & Minuman": 5000, "2025-10|Transportasi": 10000},
                )

                # 15000 dari value fake_ws
                # 5000 dari generate_dummy_file
                self.assertEqual(
                    rows_for_update,
                    [{"range": "C2", "values": [[20000]]}],  # 15000 + 5000
                )

                self.assertEqual(rows_for_append, [["2025-10", "Transportasi", 10000]])

                # ubah values berdasarkan baris agar data sheets berubah sesuai update
                for item in rows_for_update:
                    index = int(item["range"][1]) - 1
                    get_all_values_default[index][-1] = item["values"][0][0]

                # tambah data berdasarkan baris agar data sheets berubah sesuai yang terbaru
                for item in rows_for_append:
                    get_all_values_default.append(item)

                fake_ws.get_all_values.return_value = get_all_values_default

                # ubah data file csv > ubah month
                with dummy_file.open("w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "category", "subcategory", "price"])
                    writer.writerow(
                        ["2025-11-23", "Makanan & Minuman", "Cemilan", 5000]
                    )
                    writer.writerow(["2025-10-23", "Transportasi", "Tiket Umum", 10000])

                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    rows_for_update, rows_for_append = (
                        obj.process_file_category_expense()
                    )
                    obj.change_data_model()

                # 15000 dari value fake_ws kategori makanan
                # 5000 dari generate_dummy_file di ubah month nya dari bulan 10 > 11
                # tadinya 20000 karena month berubah -5000
                self.assertEqual(
                    rows_for_update,
                    [
                        {
                            "range": "C3",
                            "values": [[10000]],  # Transportasi
                        },
                        {
                            # range makanan -5000 karena monthnya di ubah
                            "range": "C2",
                            "values": [[15000]],  # 20000 - 5000
                        },
                    ],
                )

                self.assertEqual(
                    rows_for_append, [["2025-11", "Makanan & Minuman", 5000]]
                )

                model.refresh_from_db()
                self.assertEqual(
                    model.latest_category_expense_data,
                    {"2025-11|Makanan & Minuman": 5000, "2025-10|Transportasi": 10000},
                )

    def test_api_error(self, mock_logger):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # --- Data di Google Sheet sebelum reprocess ---
                get_all_values_default = [
                    ["month", "category", "total_expense"],
                    ["2025-10", "Makanan & Minuman", 15000],
                ]

                fake_ws.get_all_values.return_value = get_all_values_default

                fake_response = MagicMock()
                fake_response.json.return_value = {
                    "error": {"message": "API Error", "code": "Error"}
                }
                fake_response.text = "API Error"
                fake_response.status_code = 500

                fake_ws.batch_update.side_effect = gspread.exceptions.APIError(
                    fake_response
                )

                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    with self.assertRaises(gspread.exceptions.APIError):
                        rows_for_update, rows_for_append = (
                            obj.process_file_category_expense()
                        )
                    obj.change_data_model()

                mock_logger.exception.assert_any_call(
                    "API error saat mengubah sheet: APIError: [Error]: API Error"
                )

    def test_except_error(self, mock_logger):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
                fake_gc = MagicMock()
                fake_sh = MagicMock()
                fake_ws = MagicMock()

                mock_authorize.return_value = fake_gc
                fake_gc.open_by_key.return_value = fake_sh
                fake_sh.worksheet.return_value = fake_ws

                # --- Data di Google Sheet sebelum reprocess ---
                get_all_values_default = [
                    ["month", "category", "total_expense"],
                    ["2025-10", "Makanan & Minuman", 15000],
                ]

                fake_ws.get_all_values.return_value = get_all_values_default

                fake_ws.batch_update.side_effect = Exception("Except Error")

                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }

                obj = ProcessFile(file)
                if obj.check_changes_data_file():
                    obj.group_file_data()
                    with self.assertRaises(Exception):
                        rows_for_update, rows_for_append = (
                            obj.process_file_category_expense()
                        )
                    obj.change_data_model()

                mock_logger.exception.assert_any_call(
                    "Gagal memperbarui sheet: Except Error"
                )
