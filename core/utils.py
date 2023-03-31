from decouple import config
from django.contrib.auth import get_user_model
from django.utils import lorem_ipsum
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import response, status
from rest_framework_simplejwt.tokens import RefreshToken


def register_social_user(email, name):
    user = get_user_model().objects.filter(email=email).first()

    if not user:
        username = lorem_ipsum.words(2, common=False)
        username = "".join(username.split(" "))
        get_user_model().objects.create_user(
            username=username, email=email, password=config("SOCIAL_PASSWORD")
        )

    refresh = RefreshToken.for_user(user)
    return {
        "tokens": {"access": refresh.access, "refresh": refresh},
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.profile.full_name,
        },
    }


class Google:
    """Google class to fetch the user info and return it"""

    @staticmethod
    def validate(auth_token):
        """
        validate method Queries the Google oAUTH2 api to fetch the user info
        """
        try:
            idinfo = id_token.verify_oauth2_token(auth_token, google_requests.Request())

            if "accounts.google.com" in idinfo["iss"]:
                return idinfo
        except:
            return response.Response(
                {
                    "error": "The token is either invalid or has expired",
                    "status": False,
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
