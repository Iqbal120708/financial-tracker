from django.db import models
from django.utils.timezone import now


# Create your models here.
class BaseModel(models.Model):
    created_at = models.DateTimeField(editable=False)
    updated_at = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        if not self.pk and not self.created_at:
            self.created_at = now()
        self.updated_at = now()

        super().save(*args, **kwargs)

    class Meta:
        abstract = True
