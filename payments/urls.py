from django.urls import path 
from . import views

urlpatterns = [
    path("add-payment-card/", views.AddPaymentCardView.as_view()),
    path("payment-methods/", views.PaymentMethodList.as_view()),
    path("make-payment/", views.MakePayment.as_view()),
]
