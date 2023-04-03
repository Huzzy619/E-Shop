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

from core.signals import complete_order_signal, reset_password_signal, resend_email_verification_code
from .models import Profile, User, UserSettings
from .otp import OTPGenerator
from .serializers import (
    ChangePasswordSerializer,
    FacebookSocialAuthSerializer,
    GoogleSocialAuthSerializer,
    LoginSerializer,
    OTPChangePasswordSerializer,
    OTPSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ResendEmailVerificationSerializer, UserSettingsSerializer,
)
from shop.models import Notification

class ProfileView(GenericAPIView):
    """
    Provides a Summary detail containing the Profile Information

    of the currently logged in User.

    Provides an interface to update profile

    Args:
        Authentication Access Token (JWT)

    Returns:
        object: profile
    """

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
        user = request.user
        profile = Profile.objects.get(user=user)
        serializer = self.serializer_class(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # * Update the database first and last name columns
        if full_name := serializer.validated_data.get("full_name", ""):
            name_split = full_name.split(" ")
            if len(name_split) >= 2:
                user.first_name = name_split[0].strip()
                user.last_name = name_split[1].strip()
                user.save()

        data = serializer.data
        data["email"] = request.user.email
        data["status"] = True
        return Response(data, status=status.HTTP_200_OK)


class RegisterView(GenericAPIView):
    """
    Create an account

    Returns:

        new_user: A newly registered user
    """

    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
                {
                    "message": "Registered successfully. Check email for OTP",
                    "status": True,
                },
                status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """
    Login with either Username or Email & Password to get Authentication tokens

    Args:

        Login credentials (_type_): username/password OR email/password

    Returns:

        message: success

        tokens: access and refresh

        user: user profile details
    """

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
                    {"message": "Email/Username or password is incorrect", "status": False},
                    status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                    {
                        "message": "Account is not active, contact the admin",
                        "status": False,
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_verified:
            return Response(
                    {"message": "You must verify your email first", "status": False},
                    status=status.HTTP_401_UNAUTHORIZED,
            )

        request.data["username"] = username__email
        tokens = super().post(request)
        return Response(
                {
                    "status": True,
                    "message": "Logged in successfully",
                    "tokens": tokens.data,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.profile.full_name,
                        "date_of_birth": user.profile.date_of_birth,
                        "phone": user.profile.phone if user.profile.phone != "" else None,
                        "gender": user.profile.gender
                        if user.profile.gender != "None"
                        else None,
                        "image": user.profile.image
                        if user.profile.image != "default.jpg"
                        else None,
                    },
                },
                status=status.HTTP_200_OK,
        )


class RefreshView(TokenRefreshView):
    """
    To get new access token after the initial one expires or becomes invalid

    Args:
        refresh_token

    Returns:
        access_token
    """

    serializer_class = TokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_token = serializer.validated_data["access"]
        return Response(
                {"access": access_token, "status": True}, status=status.HTTP_200_OK
        )


class GetOTPView(GenericAPIView):
    """
    Call this endpoint with a registered email to get OTP

    Args:
        Email

    Returns:
        OTP: For 2 Factor Authentication and to complete registration
    """

    serializer_class = OTPSerializer

    def get(self, request, email):
        try:
            user = get_user_model().objects.get(email=email)
        except get_user_model().DoesNotExist:
            return Response(
                    {"status": False, "message": "No user with the provided email"},
                    status=status.HTTP_404_NOT_FOUND,
            )

        otp_gen = OTPGenerator(user_id=user.id)

        otp = otp_gen.get_otp()

        if "order" in request.get_full_path():
            complete_order_signal.send(
                    __class__, code=otp, name=user.username, email=user.email
            )
        elif "email-verify-code" in request.get_full_path():
            resend_email_verification_code.send(
                    __class__, code=otp, name=user.username, email=user.email
            )

        else:
            reset_password_signal.send(
                    __class__, code=otp, name=user.username, email=user.email
            )

        return Response(
                {"message": "OTP sent to the provided email", "status": True},
                status=status.HTTP_200_OK,
        )


class VerifyOTPView(GenericAPIView):
    """
    Verify OTP against the provided email

    Args:
        otp (string)
        email (user_email)

    Returns:
        message: success/failure
    """

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
            if not user.is_verified:
                user.is_verified = True
                user.save()

                notification = Notification.objects.create(
                    type="ACTIVITY", title="Account setup Successful", desc = "Your account has been created and verified successfully")
                notification.users.add(user)

            return Response(
                    {"message": "2FA successfully completed", "status": True},
                    status=status.HTTP_202_ACCEPTED,
            )

        return Response({"message": "Invalid otp"}, status=status.HTTP_403_FORBIDDEN)


class OTPChangePasswordView(GenericAPIView):
    """
    OTPChange password

    """

    serializer_class = OTPChangePasswordSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        password = serializer.validated_data["password"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                    {"message": "Account not found", "status": "failed"},
                    status=status.HTTP_404_NOT_FOUND,
            )

        otp_gen = OTPGenerator(user_id=user.id)

        check = otp_gen.check_otp(str(code))
        if not check:
            return Response(
                    {
                        "message": "Code has expired or Incorrect. Request for another",
                        "status": "failed",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
            )

        if user.check_password(password):
            return Response(
                    {
                        "message": "New password cannot be same as old password",
                        "status": "failed",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save()
        return Response(
                {"message": "Password updated successfully", "status": "success"},
                status=status.HTTP_200_OK,
        )


class ChangePasswordView(GenericAPIView):
    """
    Change password

    """

    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        password = serializer.validated_data["password1"]

        try:
            password_validation.validate_password(password, request.user)
        except Exception as e:
            return Response(
                    {"message": e, "status": False}, status=status.HTTP_403_FORBIDDEN
            )

        request.user.set_password(password)
        request.user.save()
        return Response(
                {"message": "Password updated successfully", "status": True},
                status=status.HTTP_200_OK,
        )


class GoogleSocialAuthView(APIView):
    """
    Login with Google by providing Auth_token

    Args:
        Auth_token
    """

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
        data["status"]: True
        return Response(data, status=status.HTTP_200_OK)


class FacebookSocialAuthView(APIView):
    serializer_class = FacebookSocialAuthSerializer

    def post(self, request):
        """
        POST with "auth_token"
        Send an access token as from facebook to get user information
        """

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data["status"] = True
        return Response(data, status=status.HTTP_200_OK)


class UserSettingsView(GenericAPIView):
    """
    Get and update User settings


    """

    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSettings.objects.filter(user=self.request.user)

    def get(self, request):
        instance = self.get_queryset().first()
        serializer = self.serializer_class(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        instance = self.get_queryset().first()
        serializer = self.serializer_class(instance, request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResendEmailVerificationView(GenericAPIView):
    serializer_class = ResendEmailVerificationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "Account not found", "status": "failed"}, status=status.HTTP_404_NOT_FOUND)
        if user.is_verified:
            return Response({"message": "Account already verified. Log in", "status": "success"},
                            status=status.HTTP_200_OK)
        return Response({"message": "Verification code sent successfully", "status": "success"},
                        status=status.HTTP_200_OK)
