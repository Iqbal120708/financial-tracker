from django.db import models
from core.models import BaseModel
from django.core.exceptions import ValidationError


# Create your models here.
class FileIntegrity(BaseModel):
    filename = models.CharField(max_length=13, unique=True)  # max file: data_9999.csv
    hash_data = models.CharField(max_length=64)
    last_checked = models.DateTimeField()
    # menyimpan nilai terakhir hasil pemrosesan file bagian category expense
    latest_category_expense_data = models.JSONField(default=dict)
    # menyimpan nilai terakhir hasil pemrosesan file bagian monthly expense
    latest_monthly_expense_data = models.JSONField(default=dict)

    def clean(self):
        file = self.filename
        str_number = last_file.file_name.split("_")[1].split(".")[0]
        if not (
            file.startswith("data_") and file.endswith(".csv") and str_number.isdigit()
        ):
            raise ValidationError(
                {
                    "filename": "Nama file harus dimulai dengan 'data_' dan diakhiri '.csv'."
                }
            )
