from django.test import TestCase, override_settings
#from finlogic.models import FileIntegrity
from unittest.mock import patch
from pathlib import Path
import tempfile
#from django.core import mail
#from django.utils.timezone import now
# from freezegun import freeze_time
import csv
from finlogic.file_processors import ProcessFile
#import hashlib
from finlogic.tests.helper_test import generate_dummy_file, generate_fake_hash
    
    
# Create your tests here.
@patch("finlogic.file_processors.logger")
@patch("finlogic.file_processors.hashlib.sha256")
class TestCheckChangesDataFile(TestCase):
    def test_complete_data_fields(self, mock_sha256, mock_logger):
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
                data_category, data_monthly = obj.group_file_data()
                
                self.assertEqual(data_category, 
                    {"2025-10": 
                        {
                            "Makanan & Minuman": [5000],
                            "Transportasi": [10000]
                        }
                    }
                )
                
                self.assertEqual(data_monthly, 
                    {
                        "2025-10": {"2025-10-23": [5000, 10000]},
                    }
                )
                
                mock_logger.info.assert_any_call("Melakukan pengambilan dan pengelompokkan data file")
                mock_logger.info.assert_any_call("Pengelompokan data dari file data_1.csv telah selesai diproses")
    
    def test_missing_data_fields(self, mock_sha256, mock_logger):
        generate_fake_hash(mock_sha256)
    
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path, dummy_file = generate_dummy_file(tmpdir)

            with dummy_file.open("a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["", "Makanan & Minuman", "", 10000])
        
            with patch("finlogic.file_processors.Path", return_value=fake_path):
                file = {
                    "is_new_file": True,
                    "file_name": "data_1.csv",
                    "file": dummy_file,
                }
                obj = ProcessFile(file)
                data_category, data_monthly = obj.group_file_data()
                
                self.assertEqual(data_category, 
                    {"2025-10": 
                        {
                            "Makanan & Minuman": [5000],
                            "Transportasi": [10000]
                        }
                    }
                )
                
                self.assertEqual(data_monthly, 
                    {
                        "2025-10": {"2025-10-23": [5000, 10000]},
                    }
                )
                
                mock_logger.info.assert_any_call("Melakukan pengambilan dan pengelompokkan data file")
                mock_logger.warning.assert_any_call("Baris 3: Data kosong pada field date, subcategory di file data_1.csv")
                mock_logger.info.assert_any_call("Pengelompokan data dari file data_1.csv telah selesai diproses")