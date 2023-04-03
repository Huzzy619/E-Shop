# from . import new_user_signal, reset_password_signal, verification_signal
# from notifications.models import Notification
import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.signals import complete_order_signal, reset_password_signal
from utils.email_backend import send_email

from ..models import Profile, UserSettings
from ..otp import OTPGenerator


@receiver(post_save, sender=get_user_model())
def create_user_profile_and_settings(instance, created, **kwargs):
    if created:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        Profile.objects.create(user=instance)
        UserSettings.objects.create(user=instance)

        code = OTPGenerator(user_id=instance.id).get_otp()
        stripe.Customer.create()
        send_email(
            subject="Complete your registration",
            message="Registration code",
            recipients=[instance.email],
            template="email/registration.html",
            context={"code": code, "name": instance.username},
        )

        customer = stripe.Customer.create(email=instance.email)

        instance.cus_id = customer.id
        instance.save()


@receiver(reset_password_signal)
def send_pasword_reset_email(**kwargs):
    send_email(
        subject="Reset Your Password",
        message="Password Reset",
        recipients=[kwargs["email"]],
        template="email/reset_password.html",
        context={"code": kwargs["code"], "name": kwargs["name"]},
    )


@receiver(complete_order_signal)
def send_complete_order_email(**kwargs):
    send_email(
        subject="Complete Order",
        message="Code to Complete order",
        recipients=[kwargs["email"]],
        template="email/complete_order.html",
        context={"code": kwargs["code"], "name": kwargs["name"]},
    )
