import stripe
from django.conf import settings
from rest_framework import serializers

from .models import PaymentMethod


class PaymentCardSerializer(serializers.Serializer):
    card_number = serializers.IntegerField()
    expiry_month = serializers.IntegerField()
    expiry_year = serializers.IntegerField()
    cvc = serializers.IntegerField()
    card_holder_name = serializers.CharField(max_length=100)

    def validate(self, data):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        card_number = data.get("card_number")
        expiry_month = data.get("expiry_month")
        expiry_year = data.get("expiry_year")
        cvc = data.get("cvc")

        if not len(str(card_number)) == 16:
            raise serializers.ValidationError(
                {"card_number": "Value must be 16 digits", "status": False}
            )

        if not str(expiry_month).zfill(2).isdigit():
            raise serializers.ValidationError(
                {"expiry_month": "Value must be 2 digits", "status": False}
            )

        if not len(str(expiry_year)) == 2:
            raise serializers.ValidationError(
                {"expiry_year": "Value must be 2 digits", "status": False}
            )

        if not len(str(cvc)) == 3:
            raise serializers.ValidationError(
                {"cvc": "Value must be 3 digits", "status": False}
            )

        user = self.context["request"].user
        try:
            customer = stripe.Customer.retrieve(user.cus_id)
        except stripe.error.InvalidRequestError:
            # If user does not have a customer object, create one in Stripe
            customer = stripe.Customer.create(email=user.email)
            user.cus_id = customer.id
            user.save()

        # Check if the new card details already exist in the customer's payment methods
        existing_payment_methods = stripe.PaymentMethod.list(
            customer=user.cus_id, type="card"
        )
        for pm in existing_payment_methods["data"]:
            if (
                pm.card.last4 == str(card_number)[-4:]
                and str(pm.card.exp_month)[-2:] == str(expiry_month)
                and pm.card.exp_year == expiry_year
            ):
                raise serializers.ValidationError(
                    {
                        "message": "A payment method with the same card details already exists",
                        "status": False,
                    }
                )

        # If loop completes without finding a match, create a new PaymentMethod instance
        pm = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": data["card_number"],
                "exp_month": data["expiry_month"],
                "exp_year": data["expiry_year"],
                "cvc": data["cvc"],
            },
            billing_details={"name": data["card_holder_name"]},
        )
        stripe.PaymentMethod.attach(pm.id, customer=customer.id)
        PaymentMethod.objects.create(user=user, pm_id=pm.id)

        # Return the PaymentMethod details in the response
        response_data = {
            "message": "Card added successfully",
            "data": {
                "id": pm.id,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
                "card_holder_name": data["card_holder_name"],
            },
            "status": True,
        }
        return response_data


class MakePaymentSerializer(serializers.Serializer):
    order_id = serializers.CharField()
    address_id = serializers.IntegerField()
    card_id = serializers.CharField()
