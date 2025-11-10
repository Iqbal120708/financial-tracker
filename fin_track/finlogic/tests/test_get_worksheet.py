from django.test import TestCase
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
from finlogic.file_processors import ProcessFile
from finlogic.tests.helper_test import generate_dummy_file
import tempfile
from django.conf import settings
import json
import gspread


@patch("finlogic.file_processors.logger")
class TestWorksheet(TestCase):
    def test_success_not_data(self, mock_logger):
        with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
            fake_gc = MagicMock()
            fake_sh = MagicMock()
            fake_ws = MagicMock()

            mock_authorize.return_value = fake_gc
            fake_gc.open_by_key.return_value = fake_sh
            fake_sh.worksheet.return_value = fake_ws

            fake_ws.get_all_values.return_value = [
                ["month", "category", "total_expense"]
            ]

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            obj = ProcessFile(file)
            worksheet, data_rows, lookup = obj.get_worksheet("Pengeluaran Category")

            self.assertEqual(worksheet, fake_ws)
            self.assertEqual(data_rows, [])
            self.assertEqual(lookup, {})

    def test_success_with_data(self, mock_logger):
        with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
            fake_gc = MagicMock()
            fake_sh = MagicMock()
            fake_ws = MagicMock()

            mock_authorize.return_value = fake_gc
            fake_gc.open_by_key.return_value = fake_sh
            fake_sh.worksheet.return_value = fake_ws

            fake_ws.get_all_values.return_value = [
                ["month", "category", "total_expense"],
                ["2025-11", "Transportasi", 10000],
            ]

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            obj = ProcessFile(file)
            worksheet, data_rows, lookup = obj.get_worksheet("Pengeluaran Category")

            self.assertEqual(worksheet, fake_ws)
            self.assertEqual(data_rows, [["2025-11", "Transportasi", 10000]])
            self.assertEqual(lookup, {})

    def test_worksheet_not_found(self, mock_logger):
        with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
            fake_gc = MagicMock()
            fake_sh = MagicMock()
            fake_ws = MagicMock()

            mock_authorize.return_value = fake_gc
            fake_gc.open_by_key.return_value = fake_sh
            fake_sh.worksheet.side_effect = gspread.exceptions.WorksheetNotFound(
                "File tidak ditemukan"
            )

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            with self.assertRaises(gspread.exceptions.WorksheetNotFound):
                obj = ProcessFile(file)
                obj.get_worksheet("Pengeluaran Category")

            mock_logger.error.assert_any_call(
                "Worksheet 'Pengeluaran Category' tidak ditemukan."
            )

    def test_exception(self, mock_logger):
        with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
            fake_gc = MagicMock()
            fake_sh = MagicMock()
            fake_ws = MagicMock()

            mock_authorize.return_value = fake_gc
            fake_gc.open_by_key.return_value = fake_sh
            fake_sh.worksheet.side_effect = Exception("Error Worksheet")

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            with self.assertRaises(Exception):
                obj = ProcessFile(file)
                obj.get_worksheet("Pengeluaran Category")

            mock_logger.exception.assert_any_call(
                "Gagal mengambil worksheet: Error Worksheet"
            )

    def test_header_category_invalid(self, mock_logger):
        with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
            fake_gc = MagicMock()
            fake_sh = MagicMock()
            fake_ws = MagicMock()

            mock_authorize.return_value = fake_gc
            fake_gc.open_by_key.return_value = fake_sh
            fake_sh.worksheet.return_value = fake_ws

            # tukar posisi value list header agar error
            fake_ws.get_all_values.return_value = [
                ["category", "month", "total_expense"],
                ["2025-11", "Transportasi", 10000],
            ]

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            with self.assertRaises(Exception):
                obj = ProcessFile(file)
                obj.get_worksheet("Pengeluaran Category")
            
            mock_logger.exception.assert_any_call("Gagal mengambil worksheet: Header tidak sesuai untuk worksheet 'Pengeluaran Category'")
            
    def test_header_monthly_invalid(self, mock_logger):
        with patch("finlogic.file_processors.gspread.authorize") as mock_authorize:
            fake_gc = MagicMock()
            fake_sh = MagicMock()
            fake_ws = MagicMock()

            mock_authorize.return_value = fake_gc
            fake_gc.open_by_key.return_value = fake_sh
            fake_sh.worksheet.return_value = fake_ws

            # tukar posisi value list header agar error
            fake_ws.get_all_values.return_value = [
                ["total_expense", "month", "avg_per_day", "days_count"],
                ["2025-11", 10000, 2000, 5],
            ]

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            with self.assertRaises(Exception):
                obj = ProcessFile(file)
                obj.get_worksheet("Pengeluaran Bulanan")
            
            mock_logger.exception.assert_any_call("Gagal mengambil worksheet: Header tidak sesuai untuk worksheet 'Pengeluaran Bulanan'")