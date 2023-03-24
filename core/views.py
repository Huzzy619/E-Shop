from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError

# Create your views here.
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import Profile
from .otp import OTPGenerator
from .serializers import (
    ChangePasswordSerializer,
    GoogleSocialAuthSerializer,
    LoginSerializer,
    OTPSerializer,
    ProfileSerializer,
    RegisterSerializer,
)


class ProfileView(GenericAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = Profile.objects.get(user=request.user)
        serializer = self.serializer_class(profile)
        data = serializer.data
        data["email"] = request.user.email
        data["status"] = True
        return Response(data, status=status.HTTP_200_OK)

    def patch(self, request):
        profile = Profile.objects.get(user=request.user)
        serializer = self.serializer_class(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = serializer.data
        data["status"] = True
        return Response(data, status=status.HTTP_200_OK)


class RegisterView(GenericAPIView):
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {   
                "status": True,
                "detail": "Registered successfully. Check email for OTP",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = TokenObtainPairSerializer

    def post(self, request, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # This could be a username or email
        username__email, password = serializer.validated_data.values()

        try:
            # Check if the provided data is an email or username

            validate_email(username__email)
            username__email = (
                get_user_model().objects.get(email=username__email).get_username()
            )

        except (get_user_model().DoesNotExist, ValidationError):
            pass

        user = authenticate(request, username=username__email, password=password)

        if not user:
            return Response(
                {"error": "Invalid credentials", "status":False}, status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"error": "Account is not active, contact the admin", "status":False},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        request.data["username"] = username__email
        tokens = super().post(request)
        return Response(
            {
                "status":True,
                "detail": "Logged in successfully",
                "tokens": tokens.data,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.profile.full_name,
                },
            },
            status=status.HTTP_200_OK,
        )


class RefreshView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_token = serializer.validated_data["access"]
        return Response({"access": access_token, "status":True}, status=status.HTTP_200_OK)


class GetOTPView(GenericAPIView):
    serializer_class = OTPSerializer

    def get(self, request, email):
        user = get_object_or_404(get_user_model(), email=email)
        otp_gen = OTPGenerator(user_id=user.id)

        otp = otp_gen.get_otp()

        # * call function to send otp with email or SMS

        return Response({"code": otp, "status":True}, status=status.HTTP_200_OK)


class VerifyOTPView(GenericAPIView):
    serializer_class = OTPSerializer

    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = get_object_or_404(
            get_user_model(), email=serializer.validated_data["email"]
        )
        otp_gen = OTPGenerator(user_id=user.id)

        check = otp_gen.check_otp(serializer.validated_data["otp"])

        if check:
            # Mark user as verified

            user.is_verified = True
            user.save()

            return Response(
                {"detail": "2FA successfully completed", "status":True},
                status=status.HTTP_202_ACCEPTED,
            )

        return Response({"detail": "Invalid otp"}, status=status.HTTP_403_FORBIDDEN)


class ChangePasswordView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        password = serializer.validated_data["password1"]

        try:
            password_validation.validate_password(password, request.user)
        except Exception as e:
            return Response({"error": e, "status":False}, status=status.HTTP_403_FORBIDDEN)

        request.user.set_password(password)
        request.user.save()
        return Response(
            {"detail": "Password updated successfully", "status":True}, status=status.HTTP_200_OK
        )


class GoogleSocialAuthView(APIView):
    serializer_class = GoogleSocialAuthSerializer

    def post(self, request):
        """
        WORK IN PROGRESS

        POST with "auth_token"
        Send an id token from google to get user information
        """

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data['status']: True
        return Response(data, status=status.HTTP_200_OK)
