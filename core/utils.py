from rest_framework import status, response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


def register_social_user(email, name):
    filtered_user_by_email = User.objects.filter(email=email)

    if filtered_user_by_email.exists():
        user = filtered_user_by_email.get()
        Jwt.objects.filter(user=user).delete()

        access = get_access_token(
            {"user_id": str(user.id), "full_name": user.full_name}
        )

        refresh = get_refresh_token()

        Jwt.objects.create(user=user, access=access, refresh=refresh)
        return {"access": access, "refresh": refresh}



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