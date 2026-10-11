"""Authentication and session endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.db import get_connection
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import verify_password, create_access_token
from app.api.deps import get_current_user

router = APIRouter(prefix="", tags=["Auth"])

@router.post("/auth/login", response_model=TokenResponse)
@router.post("/v1/auth/login", response_model=TokenResponse)
def login(creds: LoginRequest):
    """Authenticate user with username and password, return signed JWT."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, hashed_password, full_name, role, created_at FROM users WHERE username = ?", (creds.username,))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(creds.password, row["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    user_info = {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": row["role"],
        "created_at": row["created_at"]
    }

    token = create_access_token({"sub": row["username"], "role": row["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_info
    }

@router.get("/auth/me", response_model=UserResponse)
@router.get("/v1/auth/me", response_model=UserResponse)
def get_current_user_profile(user: dict = Depends(get_current_user)):
    """Return authenticated user profile and assigned role."""
    return user
