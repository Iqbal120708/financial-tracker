from pathlib import Path

def get_file_csv():
    path_dummy_data = Path("/data/data/com.termux/files/home/dummy-data")
    for item in path_dummy_data.iterdir():
        if item.is_file():
            file = item.name
            if file.startswith("data_") and file.endswith(".csv"):
                print(file)
                