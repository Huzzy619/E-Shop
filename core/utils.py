import facebook
from decouple import config
from django.contrib.auth import get_user_model
from django.utils import lorem_ipsum
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import response, status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken


def register_social_user(email, name=None):
    user = get_user_model().objects.filter(email=email).first()

    if not user:
        username = lorem_ipsum.words(2, common=False)
        username = "".join(username.split(" "))
        user = get_user_model().objects.create_user(
            username=username, email=email, password=config("SOCIAL_PASSWORD")
        )

    refresh = RefreshToken.for_user(user)

    access = refresh.access_token

    return {
        "tokens": {"access": str(access), "refresh": str(refresh)},
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
                    "message": "The token is either invalid or has expired",
                    "status": False,
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )


class Facebook:
    """
    Facebook class to fetch the user info and return it
    """

    @staticmethod
    def validate(auth_token):
        """
        validate method Queries the facebook GraphAPI to fetch the user info
        """
        try:
            graph = facebook.GraphAPI(access_token=auth_token)
            profile = graph.request("/me?fields=name,email")
            return profile
        except:
            return response.Response(
                {
                    "message": "The token is either invalid or has expired",
                    "status": False,
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
