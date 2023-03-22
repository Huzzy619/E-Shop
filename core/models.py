import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from utils.validators import validate_phone_number

# Create your models here.


class User(AbstractUser):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    email = models.EmailField(unique=True)

    is_verified = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.profile.full_name


class Profile(models.Model):
    GENDER = [
        ("None", "None"),
        ("Male", "Male"),
        ("Female", "Female"),
    ]

    full_name = models.CharField(max_length=550, null=True, blank=True)
    phone = models.CharField(max_length=14, validators=[validate_phone_number])
    image = models.ImageField(default="default.jpg", upload_to="profile_pictures")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER, default="None")
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    user = models.OneToOneField(User, on_delete=models.CASCADE)


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    pass


class OTP(models.Model):
    counter = models.IntegerField(default=1)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
