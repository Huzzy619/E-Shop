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
        full_name = self.profile.full_name
        if not full_name:
            return self.username
        return full_name


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
    notification = models.BooleanField(default=True)
    sound = models.BooleanField(default=True)
    vibrate = models.BooleanField(default=True)
    special_offers = models.BooleanField(default=True)
    payments = models.BooleanField(default=True)
    cashback = models.BooleanField(default=True)
    app_updates = models.BooleanField(default=True)
    language = models.CharField(max_length=50, default='english')
    face_id = models.BooleanField(default=False)
    biometric = models.BooleanField(default=False)

class OTP(models.Model):
    counter = models.IntegerField(default=1)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
