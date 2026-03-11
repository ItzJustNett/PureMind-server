"""
OAuth authentication routes
Handles Discord and Microsoft OAuth login
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import logging
import auth
import async_managers
from oauth_providers import OAuthProvider
from database import SessionLocal
from database.models import User, Profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oauth", tags=["oauth"])


class OAuthCallbackRequest(BaseModel):
    code: str
    provider: str


@router.get("/{provider}/url")
async def get_oauth_url(provider: str):
    """Get OAuth authorization URL for a provider (discord or microsoft)"""
    try:
        if provider not in ["discord", "microsoft"]:
            raise HTTPException(status_code=400, detail="Invalid provider")

        url = await OAuthProvider.get_authorization_url(provider)

        if not url:
            raise HTTPException(
                status_code=500,
                detail=f"{provider.title()} OAuth not configured. Please set environment variables."
            )

        return {"url": url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/callback")
async def oauth_callback(data: OAuthCallbackRequest):
    """Handle OAuth callback and login/register user"""
    try:
        if data.provider not in ["discord", "microsoft"]:
            raise HTTPException(status_code=400, detail="Invalid provider")

        # Exchange code for token
        token_data = await OAuthProvider.exchange_code_for_token(data.provider, data.code)
        if not token_data:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received")

        # Get user info from provider
        user_info = await OAuthProvider.get_user_info(data.provider, access_token)
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user information")

        # Check if user exists
        db = SessionLocal()
        try:
            # Try to find user by email
            email = user_info.get("email")
            if not email:
                raise HTTPException(status_code=400, detail="Email not provided by OAuth provider")

            existing_user = db.query(User).filter(User.email == email).first()

            if existing_user:
                # User exists, log them in
                user_id = existing_user.id
                logger.info(f"Existing user logged in via {data.provider}: {email}")

            else:
                # Create new user
                username = user_info.get("username") or email.split("@")[0]

                # Ensure username is unique
                base_username = username
                counter = 1
                while db.query(User).filter(User.username == username).first():
                    username = f"{base_username}{counter}"
                    counter += 1

                # Create user with a random password (they'll use OAuth to login)
                import secrets
                random_password = secrets.token_urlsafe(32)
                password_hash = auth.hash_password(random_password)

                new_user = User(
                    username=username,
                    email=email,
                    password_hash=password_hash
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)

                user_id = new_user.id

                # Create default profile
                profile = Profile(
                    user_id=user_id,
                    name=username,
                    cat_id=0
                )
                db.add(profile)
                db.commit()

                logger.info(f"New user created via {data.provider}: {email}")

            # Generate auth token
            result, status = await async_managers.login_user_by_id_async(str(user_id))

            if status != 200:
                raise HTTPException(status_code=status, detail="Failed to generate auth token")

            return {
                "success": True,
                "token": result["token"],
                "user_id": str(user_id),
                "is_new_user": not existing_user
            }

        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
