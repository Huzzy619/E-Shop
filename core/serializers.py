from decouple import config
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from rest_framework import serializers

from .models import Profile
from .utils import Google, register_social_user


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["full_name", "date_of_birth", "phone", "gender", "image"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password1 = serializers.CharField()
    password2 = serializers.CharField()

    def validate(self, attrs):
        if not attrs["password1"] == attrs["password2"]:
            raise serializers.ValidationError(
                detail={"error": "The two password fields didn’t match.", "status":False}
            )
        

        return super().validate(attrs)

    def save(self, **kwargs):
        username, email, password, _ = self.validated_data.values()
        try:
            user = get_user_model().objects._create_user(
                username=username, email=email, password=password
            )
        except IntegrityError:
            raise serializers.ValidationError(
                detail={"error": "User with provided credentials already exists", "status":False}
            )

        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

class ChangePasswordSerializer(serializers.Serializer):
    password1 = serializers.CharField()
    password2 = serializers.CharField()

    def validate(self, attrs):
        if not attrs["password1"] == attrs["password2"]:
            raise serializers.ValidationError(
                detail={"error": "The two password fields didn’t match.", "status":False}
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
            raise serializers.ValidationError({"error": str(identifier), "status":False})

        if user_data["aud"] != config("GOOGLE_CLIENT_ID"):
            raise serializers.ValidationError(
                {"error": "Invalid credentials", "status": False}
            )

        email = user_data["email"]
        name = user_data["name"]

        return register_social_user(email=email, name=name)
