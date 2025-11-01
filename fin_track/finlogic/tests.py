from django.test import TestCase, override_settings
from .models import FileIntegrity
from unittest.mock import patch
from pathlib import Path
import tempfile
from .utils import get_file_csv
from django.core import mail
from django.utils.timezone import now
from freezegun import freeze_time
import csv

# Create your tests here.
@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SENDER_EMAIL="system@example.com",
    TARGETS_EMAIL=["target@example.com"],
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)

@freeze_time("2025-11-01 10:00:00")
class TestUtilsGetFileCsv(TestCase):
    @classmethod
    def setUpTestData(cls): 
        FileIntegrity.objects.create(
            filename="data_1.csv",
            hash_data="qwertyuioplkjhgfdsazxcvbnm",
            last_checked=now()
        )
    
    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir)

            # patch Path di modul kamu, misal 'app.tasks.Path'
            with patch("finlogic.utils.Path", return_value=fake_path):
                result = get_file_csv()
                
                self.assertIsNone(result)
                self.assertEqual(len(mail.outbox), 1)
                
                email = mail.outbox[0]
                self.assertEqual(email.subject, "Tidak Ada File di Direktori")
                self.assertEqual(email.from_email, "system@example.com")
                self.assertEqual(email.to, ["target@example.com"])
        
    @freeze_time("2025-11-02 08:00:00")
    def test_new_file_and_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir)
            dummy_file = fake_path / "data_2.csv"
            
            with dummy_file.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Category", "Price"])
                writer.writerow(["Makanan", 10000])
                writer.writerow(["Transportasi", 15000])
                
            assert dummy_file.exists()
            
            # patch Path di modul kamu, misal 'app.tasks.Path'
            with patch("finlogic.utils.Path", return_value=fake_path):
                result = get_file_csv()
                
                self.assertEqual(len(mail.outbox), 0)#gak ada email dikirim
                self.assertTrue(result["is_new_file"])
                self.assertEqual(result["file_name"], "data_2.csv")
                self.assertEqual(result["file"], dummy_file)
    
    def test_last_file_and_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir)
            dummy_file = fake_path / "data_1.csv"
            
            with dummy_file.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Category", "Price"])
                writer.writerow(["Makanan", 10000])
                writer.writerow(["Transportasi", 15000])
                
            assert dummy_file.exists()
            
            # patch Path di modul kamu, misal 'app.tasks.Path'
            with patch("finlogic.utils.Path", return_value=fake_path):
                result = get_file_csv()
                
                self.assertEqual(len(mail.outbox), 0)#gak ada email dikirim
                self.assertFalse(result["is_new_file"])
                self.assertEqual(result["file_name"], "data_1.csv")
                self.assertEqual(result["file"], dummy_file)
    
    
    def test_last_file_integrity_not_data(self):
        FileIntegrity.objects.all().delete()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir)
            dummy_file = fake_path / "data_1.csv"
            
            with dummy_file.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Category", "Price"])
                writer.writerow(["Makanan", 10000])
                writer.writerow(["Transportasi", 15000])
                
            assert dummy_file.exists()
            
            # patch Path di modul kamu, misal 'app.tasks.Path'
            with patch("finlogic.utils.Path", return_value=fake_path):
                result = get_file_csv()
                
                self.assertEqual(len(mail.outbox), 0)#gak ada email dikirim
                self.assertFalse(result["is_new_file"])
                self.assertEqual(result["file_name"], "data_1.csv")
                self.assertEqual(result["file"], dummy_file)
    
    def test_last_file_and_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir)
            dummy_file = fake_path / "file_random.txt"
            dummy_file.write_text("teks file_random")
                
            assert dummy_file.exists()
            
            # patch Path di modul kamu, misal 'app.tasks.Path'
            with patch("finlogic.utils.Path", return_value=fake_path):
                result = get_file_csv()
                
                self.assertIsNone(result)
                self.assertEqual(len(mail.outbox), 1)
                
                email = mail.outbox[0]
                body_one_line = email.body.split("\n")[0] # ambil pesan baris pertama
                
                self.assertEqual(email.subject, "File Tidak Ditemukan di Direktori")
                self.assertEqual(body_one_line, "Sistem tidak menemukan file data_1.csv di lokasi berikut:")
                self.assertEqual(email.from_email, "system@example.com")
                self.assertEqual(email.to, ["target@example.com"])