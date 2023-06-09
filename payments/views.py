import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shop.models import (
    BillingAddress,
    ColorInventory,
    Notification,
    Order,
    SizeInventory,
)

from .models import PaymentMethod
from .serializers import MakePaymentSerializer, PaymentCardSerializer


# Create your views here.
class AddPaymentCardView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentCardSerializer

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        response_data = serializer.validated_data
        return Response(response_data, status=status.HTTP_200_OK)


class PaymentMethodList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        user = request.user
        if not user.cus_id:
            return Response(
                {"message": "Payment methods returned!", "data": [], "status": False},
                status=status.HTTP_200_OK,
            )
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=user.cus_id, type="card"
            )
            cards = [
                {
                    "id": c["id"],
                    "last4": c["card"]["last4"],
                    "exp_month": c["card"]["exp_month"],
                    "exp_year": c["card"]["exp_year"],
                    "card_holder_name": c["billing_details"]["name"],
                    "brand": c["card"]["brand"],
                }
                for c in payment_methods.data
            ]

            return Response(
                {
                    "message": "Payment Methods returned!",
                    "status": True,
                    "data": cards,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            print(e)
            return Response(
                {"message": "Network error!", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MakePayment(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MakePaymentSerializer

    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        user = request.user
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order_id = data.get("order_id")
        card_id = data.get("card_id")
        address_id = data.get("address_id")

        orders = Order.objects.filter(customer=user, id__in=order_id)
        if not orders:
            return Response(
                {"message": "You don't have any order with that ID", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        address = BillingAddress.objects.filter(customer=user, id=address_id).first()
        if not address:
            return Response(
                {
                    "message": "You don't have any shipping address with that ID!",
                    "status": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method = PaymentMethod.objects.filter(user=request.user, pm_id=card_id)

        if not payment_method:
            return Response(
                {
                    "message": "You don't have a payment method with that ID!",
                    "status": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        prices = []
        for order in orders:
            if order.payment_status == "complete":
                return Response(
                    {
                        "message": f"Payment made already for {order.id} !",
                        "status": False,
                    },
                    status=status.HTTP_200_OK,
                )
            order.shipping_address = address.address
            order.save()
            prices.append(order.price)

        amount_payable = int(settings.SHIPPING_FEES) + sum(prices)

        try:
            payment = stripe.PaymentIntent.create(
                amount=int(amount_payable * 100),
                currency="usd",
                customer=user.cus_id,
                payment_method=card_id,
                confirm=True,
            )

            if payment["status"] == "succeeded":
                title = ""
                for order in orders:
                    order.payment_status = "complete"
                    order.save()

                    # Reduce quantities from inventory
                    order.product.inventory -= order.quantity

                    order.product.save()

                    if order.color:
                        c_obj = ColorInventory.objects.get(
                            product=order.product, color__name=order.color
                        )
                        c_obj.quantity -= order.quantity
                        c_obj.save()

                    if order.size:
                        s_obj = SizeInventory.objects.get(
                            product=order.product, size__size=order.size
                        )
                        s_obj.quantity -= order.quantity
                        s_obj.save()

                    # For notification title
                    title += order.product.title

                notification = Notification.objects.create(type="ACTIVITY", title=title)
                notification.users.add(user)

                return Response(
                    {
                        "message": "Payment successful",
                        "payment_data": {
                            # "tx_ref": order.id,
                            "amount": sum(prices),
                            "shipping_fees": int(settings.SHIPPING_FEES),
                        },
                        "status": True,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                order.payment_status = "failed"
                order.save()
                return Response(
                    {"message": "Payment failed", "status": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {"message": str(e), "status": False}, status=status.HTTP_400_BAD_REQUEST
            )

        
