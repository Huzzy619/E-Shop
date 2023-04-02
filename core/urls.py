from django.urls import path

from . import views

urlpatterns = [
    path('register', views.RegisterView.as_view()),

    path('login', views.LoginView.as_view()),
    path('login/google', views.GoogleSocialAuthView.as_view()),
    path("login/facebook", views.FacebookSocialAuthView.as_view()),

    path('refresh/token', views.RefreshView.as_view()), 
    path("otp/send/<str:email>", views.GetOTPView.as_view()),
    path("otp/verify", views.VerifyOTPView.as_view()),
    path("user/profile", views.ProfileView.as_view()), 
    path("change/password", views.ChangePasswordView.as_view()),
    path("user/settings", views.UserSettingsView.as_view())
]
