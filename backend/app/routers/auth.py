import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.core.auth import create_access_token, get_current_user, hash_password, verify_password
from backend.app.core.database import get_db
from backend.app.models.db_models import User
from backend.app.models.schemas import AuthResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Auth"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _public_user(user: User) -> UserResponse:
    return UserResponse(id=user.id, username=user.username, email=user.email, created_at=user.created_at, profile_number=user.profile_number)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, response: Response, db: Session = Depends(get_db)):
    username = payload.username.strip()
    email = payload.email.strip().lower()
    if not username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a user name.")
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid email address.")
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Log in instead.",
        )
    user = User(username=username, email=email, password_hash=hash_password(payload.password), profile_number=payload.profile_number)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    response.set_cookie("continuum_session", token, httponly=True, secure=request.url.scheme == "https", samesite="strict", max_age=604800, path="/")
    response.headers["Cache-Control"] = "no-store"
    return AuthResponse(access_token=token, user=_public_user(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    # Same message for unknown email and wrong password.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token = create_access_token(user.id)
    response.set_cookie("continuum_session", token, httponly=True, secure=request.url.scheme == "https", samesite="strict", max_age=604800, path="/")
    response.headers["Cache-Control"] = "no-store"
    return AuthResponse(access_token=token, user=_public_user(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return _public_user(current_user)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("continuum_session", path="/")
    response.headers["Cache-Control"] = "no-store"
    return {"status": "logged_out"}
