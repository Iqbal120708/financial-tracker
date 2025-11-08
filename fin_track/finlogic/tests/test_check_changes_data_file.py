from django.test import TestCase, override_settings
from finlogic.models import FileIntegrity
from unittest.mock import patch
from pathlib import Path
import tempfile
from django.core import mail
from django.utils.timezone import now
from freezegun import freeze_time
import csv
from finlogic.file_processors import ProcessFile
#import hashlib
from finlogic.tests.helper_test import generate_dummy_file, generate_fake_hash
    
# Create your tests here.
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SENDER_EMAIL="system@example.com",
    TARGETS_EMAIL=["target@example.com"],
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
@patch("finlogic.file_processors.logger")
@patch("finlogic.file_processors.hashlib.sha256")
class TestCheckChangesDataFile(TestCase):
    def test_new_file(self, mock_sha256, mock_logger):
        """
        test ketika melakukan check perubahan data tapi file nya baru
        """
        generate_fake_hash(mock_sha256)
    
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with patch("finlogic.file_processors.Path", return_value=fake_path):
                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }
                obj = ProcessFile(file)
                is_changes = obj.check_changes_data_file()

                # False karena file baru
                self.assertTrue(is_changes)
                
                mock_logger.info.assert_any_call("Memulai pengecekan data di file")
                mock_logger.debug.assert_any_call(f"Hash file berhasil dibuat: fakehash123")
                mock_logger.info.assert_any_call("Menghentikan pengecekan karena file baru")

    def test_old_file_with_hash_data_not_changes(self, mock_sha256, mock_logger):
        """
        test ketika melakukan check perubahan data, file sama tapi data tidak ada perubahan dengan pengecekan data file sebelumnya 
        """
        generate_fake_hash(mock_sha256)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            # buat data baru agar bisa bandingkan hash_data
            with freeze_time("2025-11-06 00:00:00"):
                FileIntegrity.objects.create(
                    filename=dummy_file.name,
                    hash_data="fakehash123",
                    last_checked=now(),
                )

            with patch("finlogic.file_processors.Path", return_value=fake_path):
                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }
                obj = ProcessFile(file)
                is_changes = obj.check_changes_data_file()

                # False karena file datanya tak berubah atau file_hash nya sama dengan hash_data model
                self.assertFalse(is_changes)
                
                mock_logger.info.assert_any_call("Memulai pengecekan data di file")
                mock_logger.debug.assert_any_call(f"Hash file berhasil dibuat: fakehash123")
                mock_logger.info.assert_any_call("Hash data lama sama dengan hash data baru. Data file tidak berubah")
                
                self.assertEqual(len(mail.outbox), 1)
                
                email = mail.outbox[0]
                
                self.assertEqual(email.subject, "Data File Tidak Berubah")
                self.assertEqual(email.from_email, "system@example.com")
                self.assertEqual(email.to, ["target@example.com"])

    def test_old_file_with_hash_data_changes(self, mock_sha256, mock_logger):
        """
        test ketika melakuksn check perubahn data, file sama dan data nya berubah dengan pengecekan data file sebelumnya
        """
        
        generate_fake_hash(mock_sha256)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            # buat data baru agar bisa bandingkan hash_data
            with freeze_time("2025-11-06 00:00:00"):
                FileIntegrity.objects.create(
                    filename=dummy_file.name,
                    hash_data="oldhash123",
                    last_checked=now(),
                )

            # ubah data file
            with dummy_file.open("a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["2025-10-23", "Transportasi", "Bensin", 15000])

            with patch("finlogic.file_processors.Path", return_value=fake_path):
                file = {
                    "is_new_file": False,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }
                obj = ProcessFile(file)
                is_changes = obj.check_changes_data_file()

                # True karena data file berubah
                self.assertTrue(is_changes)
                
                mock_logger.info.assert_any_call("Memulai pengecekan data di file")
                mock_logger.debug.assert_any_call(f"Hash file berhasil dibuat: fakehash123")
                mock_logger.info.assert_any_call("Data file berubah")
