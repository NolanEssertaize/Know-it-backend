"""
Google OAuth integration.
Handles Google OAuth2 flow and ID token verification.
"""

import logging
from typing import Optional

import httpx
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.auth.schemas import OAuthUserInfo
from app.config import get_settings
from app.core.exceptions import OAuthError

logger = logging.getLogger(__name__)
settings = get_settings()

# Google OAuth URLs
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleOAuth:
    """Google OAuth2 handler."""

    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret

    async def exchange_code(
            self,
            code: str,
            redirect_uri: str,
    ) -> dict:
        """
        Exchange authorization code for tokens.

        Args:
            code: Authorization code from Google
            redirect_uri: Redirect URI used in auth request

        Returns:
            Token response with access_token, id_token, etc.

        Raises:
            OAuthError: If token exchange fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )

                if response.status_code != 200:
                    logger.error(f"[GoogleOAuth] Token exchange failed: {response.text}")
                    raise OAuthError("Failed to exchange authorization code")

                return response.json()

            except httpx.RequestError as e:
                logger.error(f"[GoogleOAuth] Request error: {e}")
                raise OAuthError("Failed to connect to Google OAuth")

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """
        Get user info from Google using access token.

        Args:
            access_token: Google access token

        Returns:
            OAuthUserInfo with user details

        Raises:
            OAuthError: If request fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code != 200:
                    logger.error(f"[GoogleOAuth] User info request failed: {response.text}")
                    raise OAuthError("Failed to get user info from Google")

                data = response.json()

                return OAuthUserInfo(
                    email=data["email"],
                    google_id=data["id"],
                    full_name=data.get("name"),
                    picture_url=data.get("picture"),
                    email_verified=data.get("verified_email", False),
                )

            except httpx.RequestError as e:
                logger.error(f"[GoogleOAuth] Request error: {e}")
                raise OAuthError("Failed to connect to Google")

    def verify_id_token(self, token: str) -> OAuthUserInfo:
        """
        Verify Google ID token (for mobile app authentication).

        Args:
            token: Google ID token from Sign-In

        Returns:
            OAuthUserInfo with user details

        Raises:
            OAuthError: If verification fails
        """
        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self.client_id,
            )

            # Check issuer
            if idinfo["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise OAuthError("Invalid token issuer")

            return OAuthUserInfo(
                email=idinfo["email"],
                google_id=idinfo["sub"],
                full_name=idinfo.get("name"),
                picture_url=idinfo.get("picture"),
                email_verified=idinfo.get("email_verified", False),
            )

        except ValueError as e:
            logger.error(f"[GoogleOAuth] ID token verification failed: {e}")
            raise OAuthError("Invalid Google ID token")

    async def authenticate(
            self,
            code: Optional[str] = None,
            redirect_uri: Optional[str] = None,
            id_token_str: Optional[str] = None,
    ) -> OAuthUserInfo:
        """
        Authenticate user via Google OAuth.

        Supports two flows:
        1. Web flow: code + redirect_uri
        2. Mobile flow: id_token

        Args:
            code: Authorization code (web flow)
            redirect_uri: Redirect URI (web flow)
            id_token_str: ID token from Google Sign-In (mobile flow)

        Returns:
            OAuthUserInfo with user details

        Raises:
            OAuthError: If authentication fails
        """
        if id_token_str:
            # Mobile flow: verify ID token directly
            return self.verify_id_token(id_token_str)

        if code and redirect_uri:
            # Web flow: exchange code for tokens
            tokens = await self.exchange_code(code, redirect_uri)

            # Get user info using access token
            return await self.get_user_info(tokens["access_token"])

        raise OAuthError("Either id_token or code with redirect_uri required")

