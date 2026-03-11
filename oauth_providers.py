"""
OAuth provider configurations and handlers
Supports Discord and Microsoft authentication
"""
import os
import httpx
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

# OAuth Configuration from environment variables
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:3000/auth/discord/callback")

MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:3000/auth/microsoft/callback")

# OAuth URLs
DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"

MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_USER_URL = "https://graph.microsoft.com/v1.0/me"


class OAuthProvider:
    """Base OAuth provider class"""

    @staticmethod
    async def get_authorization_url(provider: str) -> Optional[str]:
        """Get OAuth authorization URL for the provider"""
        if provider == "discord":
            if not DISCORD_CLIENT_ID:
                return None
            return (
                f"{DISCORD_AUTH_URL}?"
                f"client_id={DISCORD_CLIENT_ID}&"
                f"redirect_uri={DISCORD_REDIRECT_URI}&"
                f"response_type=code&"
                f"scope=identify%20email"
            )

        elif provider == "microsoft":
            if not MICROSOFT_CLIENT_ID:
                return None
            return (
                f"{MICROSOFT_AUTH_URL}?"
                f"client_id={MICROSOFT_CLIENT_ID}&"
                f"redirect_uri={MICROSOFT_REDIRECT_URI}&"
                f"response_type=code&"
                f"scope=openid%20profile%20email"
            )

        return None

    @staticmethod
    async def exchange_code_for_token(provider: str, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token"""
        try:
            async with httpx.AsyncClient() as client:
                if provider == "discord":
                    data = {
                        "client_id": DISCORD_CLIENT_ID,
                        "client_secret": DISCORD_CLIENT_SECRET,
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": DISCORD_REDIRECT_URI
                    }
                    response = await client.post(
                        DISCORD_TOKEN_URL,
                        data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )

                elif provider == "microsoft":
                    data = {
                        "client_id": MICROSOFT_CLIENT_ID,
                        "client_secret": MICROSOFT_CLIENT_SECRET,
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": MICROSOFT_REDIRECT_URI
                    }
                    response = await client.post(
                        MICROSOFT_TOKEN_URL,
                        data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )

                else:
                    return None

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Token exchange failed: {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return None

    @staticmethod
    async def get_user_info(provider: str, access_token: str) -> Optional[Dict]:
        """Get user information from OAuth provider"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}

                if provider == "discord":
                    response = await client.get(DISCORD_USER_URL, headers=headers)
                elif provider == "microsoft":
                    response = await client.get(MICROSOFT_USER_URL, headers=headers)
                else:
                    return None

                if response.status_code == 200:
                    user_data = response.json()

                    # Normalize user data across providers
                    if provider == "discord":
                        return {
                            "id": user_data.get("id"),
                            "email": user_data.get("email"),
                            "username": user_data.get("username"),
                            "avatar": user_data.get("avatar"),
                            "provider": "discord"
                        }

                    elif provider == "microsoft":
                        return {
                            "id": user_data.get("id"),
                            "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                            "username": user_data.get("displayName") or user_data.get("givenName"),
                            "provider": "microsoft"
                        }

                else:
                    logger.error(f"Failed to get user info: {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
