from django.db import models
from core.models import BaseModel

# Create your models here.
class FileIntegrity(BaseModel):
    filename = models.CharField(max_length=13) # max file: data_9999.csv
    hash_data = models.CharField(max_length=64)
    last_checked = models.DateTimeField()