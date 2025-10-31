import warnings

from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class UserDeleteWarning(Warning):
    pass


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"  # login pakai email
    REQUIRED_FIELDS = ["username"]  # username masih ada, tapi bukan buat login

    def __str__(self):
        return self.email

    def delete(self, *args, **kwargs):
        warnings.warn(
            "method delete() di model User dipanggil! Gunakan method soft_delete() untuk menghapus user",
            category=UserDeleteWarning,
            stacklevel=2,
        )
        return super().delete(*args, **kwargs)

    def soft_delete(self, *args, **kwargs):
        self.is_active = False
        self.save()
