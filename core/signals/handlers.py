from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

# from utils.email_backend import mailjet_email_backend, send_email

from ..models import Profile, UserSettings
# from ..otp import OTPGenerator
# from . import new_user_signal, reset_password_signal, verification_signal
# from notifications.models import Notification


@receiver(post_save, sender=get_user_model())
def create_user_profile_and_settings(instance, created, **kwargs):
    if created:
        Profile.objects.create(
            user=instance)
        UserSettings.objects.create(user=instance)

