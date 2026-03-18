from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas import LoginRequest, RefreshTokenRequest, TokenResponse, UserView


router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access_token = create_access_token(user.id, user.role)
    refresh_token, token_id, expires_at = create_refresh_token(user.id, user.role)
    db.add(RefreshToken(user_id=user.id, token_id=token_id, expires_at=expires_at))
    db.flush()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserView.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        decoded = decode_token(payload.refresh_token)
    except Exception as exc:  # pragma: no cover - jwt variations
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    stored = db.query(RefreshToken).filter(RefreshToken.token_id == decoded.get("jti")).first()
    if not stored or stored.revoked_at is not None or stored.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked or expired")

    stored.revoked_at = datetime.utcnow()
    user = db.get(User, decoded["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout")
def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> dict:
    try:
        decoded = decode_token(payload.refresh_token)
    except Exception:
        return {"ok": True}
    stored = db.query(RefreshToken).filter(RefreshToken.token_id == decoded.get("jti")).first()
    if stored and stored.revoked_at is None:
        stored.revoked_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserView)
def me(current_user: User = Depends(get_current_user)) -> UserView:
    return UserView.model_validate(current_user)
