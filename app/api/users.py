from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, cast
from app.core.database import get_db
from app.middleware.auth import get_current_active_user, get_admin_user
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.user import UserResponse, UserUpdate, UserList
from app.utils.audit import audit_service

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user profile"""
    old_values = {
        "email": cast(str, current_user.email),
        "username": cast(str, current_user.username)
    }
    
    # Check for conflicts if updating email or username
    if user_update.email and user_update.email != cast(str, current_user.email):
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        setattr(current_user, 'email', user_update.email)
    
    if user_update.username and user_update.username != cast(str, current_user.username):
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        setattr(current_user, 'username', user_update.username)
    
    db.commit()
    db.refresh(current_user)
    
    # Log the update
    await audit_service.log_action(
        db=db,
        user_id=cast(int, current_user.id),
        action="USER_PROFILE_UPDATED",
        old_values=old_values,
        new_values={
            "email": cast(str, current_user.email),
            "username": cast(str, current_user.username)
        }
    )
    
    return current_user


@router.get("/", response_model=UserList)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: List all users with pagination"""
    offset = (page - 1) * size
    
    users = db.query(User).offset(offset).limit(size).all()
    total = db.query(User).count()
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "size": size
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: Get specific user details"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/{user_id}/refresh-tokens")
async def get_user_refresh_tokens(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: View user's active refresh tokens"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False
    ).all()
    
    return {
        "user_id": user_id,
        "active_tokens": len(tokens),
        "tokens": [
            {
                "id": cast(int, token.id),
                "created_at": token.created_at,
                "expires_at": token.expires_at
            }
            for token in tokens
        ]
    }


@router.delete("/{user_id}/refresh-tokens")
async def revoke_user_tokens(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Admin only: Revoke all refresh tokens for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Revoke all active tokens
    tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False
    ).all()
    
    for token in tokens:
        setattr(token, 'is_revoked', True)
    
    db.commit()
    
    # Log the action
    await audit_service.log_action(
        db=db,
        user_id=cast(int, admin_user.id),
        action="USER_TOKENS_REVOKED",
        new_values={"target_user_id": user_id, "tokens_revoked": len(tokens)}
    )
    
    return {"message": f"Revoked {len(tokens)} tokens for user {user_id}"}