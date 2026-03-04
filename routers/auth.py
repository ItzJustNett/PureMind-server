"""
Authentication API routes (FastAPI version with async)
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
import logging
import auth
import async_managers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# Request/Response models
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterResponse(BaseModel):
    success: bool
    user_id: str

class LoginResponse(BaseModel):
    success: bool
    token: str
    user_id: str

class LogoutResponse(BaseModel):
    success: bool
    message: str

class UserInfo(BaseModel):
    id: str
    username: str
    created_at: int

# Dependency for token validation (using async token manager)
async def get_current_user(authorization: str = Header(...)) -> dict:
    """Extract and validate token from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")

    token = authorization.split(" ")[1]

    # Import here to avoid circular imports
    import async_managers
    user_info = await async_managers.validate_token_async(token)

    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user_info

@router.post("/register", response_model=RegisterResponse)
async def register(data: RegisterRequest):
    """Register a new user"""
    try:
        result, status = auth.register_user(data.username, data.password)

        if status != 201:
            raise HTTPException(status_code=status, detail=result.get("error", "Registration failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in register: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration error: {str(e)}")

@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    """Login a user (async with TTL tokens)"""
    try:
        result, status = await async_managers.login_user_async(data.username, data.password)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Login failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in login: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")

@router.post("/logout", response_model=LogoutResponse)
async def logout(authorization: str = Header(...)):
    """Logout a user (invalidate TTL token)"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No token provided")

        token = authorization.split(" ")[1]
        result, status = await async_managers.logout_user_async(token)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Logout failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in logout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Logout error: {str(e)}")

@router.get("/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current user info"""
    try:
        user_detail = await async_managers.get_user_by_id_async(user["user_id"])

        if not user_detail:
            raise HTTPException(status_code=404, detail="User not found")

        return user_detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting user info: {str(e)}")
