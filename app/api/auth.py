from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import cast
from app.core.database import get_db
from app.core.security import token_service, password_service
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, RefreshTokenRequest
from app.schemas.user import UserResponse
from app.utils.audit import audit_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == user_data.email) | (User.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Create new user
    hashed_password = password_service.hash_password(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log registration
    await audit_service.log_action(
        db=db,
        user_id=cast(int, user.id),
        action="USER_REGISTERED",
        new_values={"username": cast(str, user.username), "email": cast(str, user.email)}
    )
    
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticate user and return tokens"""
    # Find user
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user or not password_service.verify_password(user_data.password, cast(str, user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not cast(bool, user.is_active):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Create tokens
    access_token = token_service.create_access_token({"sub": str(cast(int, user.id))})
    refresh_token = token_service.create_refresh_token({"sub": str(cast(int, user.id))})
    
    # Store refresh token in database
    refresh_token_obj = RefreshToken(
        token=refresh_token,
        user_id=cast(int, user.id),
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(refresh_token_obj)
    db.commit()
    
    # Set refresh token in HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    # Log login
    await audit_service.log_action(
        db=db,
        user_id=cast(int, user.id),
        action="USER_LOGIN"
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    # Verify refresh token
    try:
        payload = token_service.verify_token(refresh_data.refresh_token, "refresh")
        user_id = int(payload.get("sub") or "0")
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if refresh token exists and is valid
    refresh_token_obj = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_data.refresh_token,
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).first()
    
    if not refresh_token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Create new tokens (token rotation)
    new_access_token = token_service.create_access_token({"sub": str(user_id)})
    new_refresh_token = token_service.create_refresh_token({"sub": str(user_id)})
    
    # Revoke old refresh token
    setattr(refresh_token_obj, 'is_revoked', True)
    setattr(refresh_token_obj, 'replaced_by_token', new_refresh_token)
    
    # Create new refresh token record
    new_refresh_token_obj = RefreshToken(
        token=new_refresh_token,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    
    db.add(new_refresh_token_obj)
    db.commit()
    
    # Set new refresh token in cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 60 * 60
    )
    
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    refresh_data: RefreshTokenRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """Logout user and revoke refresh token"""
    # Revoke refresh token
    refresh_token_obj = db.query(RefreshToken).filter(
        RefreshToken.token == refresh_data.refresh_token
    ).first()
    
    if refresh_token_obj:
        setattr(refresh_token_obj, 'is_revoked', True)
        db.commit()
    
    # Clear cookie
    response.delete_cookie(key="refresh_token")
    
    return {"message": "Successfully logged out"}


@router.post("/revoke-token")
async def revoke_token(
    token_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Admin endpoint to revoke a specific refresh token"""
    refresh_token_obj = db.query(RefreshToken).filter(
        RefreshToken.token == token_data.refresh_token
    ).first()
    
    if refresh_token_obj:
        setattr(refresh_token_obj, 'is_revoked', True)
        db.commit()
        return {"message": "Token revoked successfully"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Token not found"
    )