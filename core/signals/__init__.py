from django.dispatch import Signal

new_user_signal = Signal()

reset_password_signal = Signal()

verification_signal = Signal()

complete_order_signal = Signal()

resend_email_verification_code = Signal()