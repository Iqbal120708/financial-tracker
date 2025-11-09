import csv
from unittest.mock import MagicMock
from pathlib import Path


def generate_dummy_file(tmpdir):
    fake_path = Path(tmpdir)
    dummy_file = fake_path / "data_1.csv"

    with dummy_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "category", "subcategory", "price"])
        writer.writerow(["2025-10-23", "Makanan & Minuman", "Cemilan", 5000])
        writer.writerow(["2025-10-23", "Transportasi", "Tiket Umum", 10000])

    assert dummy_file.exists()
    return fake_path, dummy_file


def generate_fake_hash(mock_sha256):
    mock_hash = MagicMock()
    mock_hash.hexdigest.return_value = "fakehash123"
    mock_sha256.return_value = mock_hash
