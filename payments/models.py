from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

# Create your models here.
class PaymentMethod(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    pm_id = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.user} **** **** **** {self.pm_id}"