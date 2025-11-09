from django.test import TestCase, override_settings
from unittest.mock import patch
from pathlib import Path
import tempfile
from finlogic.file_processors import ProcessFile
from finlogic.tests.helper_test import generate_dummy_file
import tempfile
from django.conf import settings
import json
import gspread


@patch("finlogic.file_processors.logger")
class TestExceptInItClass(TestCase):
    @override_settings(PATH_CREDENTIALS="/fake/file.json")
    def test_creds_not_found(self, mock_logger):

        file = {
            "is_new_file": True,
            "file_name": "data_1.csv",
            "file": None,
        }
        with self.assertRaises(FileNotFoundError):
            ProcessFile(file)

        mock_logger.error.assert_any_call(
            "File credentials tidak ditemukan di path: /fake/file.json"
        )

    def test_creds_invalid(self, mock_logger):
        with patch(
            "google.oauth2.service_account.Credentials.from_service_account_file"
        ) as mock_creds:
            mock_creds.side_effect = Exception("Error Credentials")

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            with self.assertRaises(Exception):
                ProcessFile(file)
            mock_logger.exception.assert_any_call(
                "Kredensial tidak valid: Error Credentials"
            )

    def test_gspread_invalid(self, mock_logger):
        with patch("gspread.authorize") as mock_auth:
            mock_auth.side_effect = Exception("Autorisasi gagal")

            file = {
                "is_new_file": True,
                "file_name": "data_1.csv",
                "file": None,
            }

            with self.assertRaises(Exception):
                ProcessFile(file)

            mock_logger.exception.assert_any_call(
                "Gagal menghubungkan ke Google Sheets API: Autorisasi gagal"
            )

    @override_settings(ID_FILE_GOOGLE_SHEETS="fakeid123")
    def test_spreadsheet_not_found(self, mock_logger):
        file = {
            "is_new_file": True,
            "file_name": "data_1.csv",
            "file": None,
        }

        with self.assertRaises(gspread.exceptions.SpreadsheetNotFound):
            ProcessFile(file)

        mock_logger.error.assert_any_call(
            "Tidak dapat menemukan spreadsheet dengan ID: fakeid123"
        )
