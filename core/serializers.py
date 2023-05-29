import re

from decouple import config
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.utils import IntegrityError
from rest_framework import serializers

from .models import Profile, UserSettings
from .utils import Facebook, Google, register_social_user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["full_name", "date_of_birth", "phone", "gender", "image"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField()

    # password2 = serializers.CharField()

    # def validate(self, attrs):
    #     if not attrs["password1"] == attrs["password2"]:
    #         raise serializers.ValidationError(
    #             detail={"message": "The two password fields didn’t match.", "status":False}
    #         )

    #     return super().validate(attrs)

    def save(self, **kwargs):
        username, email, password = self.validated_data.values()
        try:
            user = get_user_model().objects._create_user(
                    username=username, email=email, password=password
            )
        except IntegrityError:
            raise serializers.ValidationError(
                    detail={"message": "User with provided credentials already exists", "status": False}
            )

        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class OTPChangePasswordSerializer(serializers.Serializer):
    otp = serializers.IntegerField()
    password = serializers.CharField(max_length=50, min_length=6, write_only=True)
    email = serializers.EmailField()

    def validate(self, attrs):
        otp = attrs.get('otp', '')

        # validate code
        if not otp:
            raise serializers.ValidationError("OTP is required")

        if not re.match("^[0-9]{4}$", str(otp)):
            raise serializers.ValidationError("OTP must be a 4-digit number")

        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    password1 = serializers.CharField()
    password2 = serializers.CharField()

    def validate(self, attrs):
        if not attrs["password1"] == attrs["password2"]:
            raise serializers.ValidationError(
                    detail={"message": "The two password fields didn’t match.", "status": False}
            )

        return super().validate(attrs)


class GoogleSocialAuthSerializer(serializers.Serializer):
    auth_token = serializers.CharField()

    def validate(self, data):
        auth_token = data.get("auth_token")
        user_data = Google.validate(auth_token)

        try:
            user_data["sub"]
        except Exception as identifier:
            raise serializers.ValidationError({"message": str(identifier), "status": False})

        print(user_data["aud"])
        print(config("GOOGLE_CLIENT_ID"))
        if user_data["aud"] != config("GOOGLE_CLIENT_ID"):
            raise serializers.ValidationError(
                    {"message": "Invalid credentials", "status": False}
            )

        email = user_data["email"]
        name = user_data["name"]

        return register_social_user(email=email, name=name)


class FacebookSocialAuthSerializer(serializers.Serializer):
    """Handles serialization of facebook related data"""

    auth_token = serializers.CharField()

    def validate(self, data):
        auth_token = data.get("auth_token")
        user_data = Facebook.validate(auth_token)
        try:
            email = user_data["email"]
            return register_social_user(email=email)
        except Exception as identifier:
            print(identifier)
            raise serializers.ValidationError({"message": str(identifier)})


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        exclude = ['id', 'user']


class ResendEmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        email = attrs.get('email', '')

        # validate email
        try:
            validate_email(email)
        except ValidationError:
            raise serializers.ValidationError("Invalid email format")
        return attrs
