"""
SYNAPSE AI — Secure Authentication & Authorization Engine.

Provides:
- Bcrypt password hashing and verification
- Robust JWT generation, signing, and verification
- FastAPI dependency for current user resolution
- Multi-tenant backend ownership verification for projects, sessions, and reports
- Safe credential and secret handling via environment variables
"""

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Report, ResearchProject, ResearchSession, User, generate_uuid, utc_now
from db.session import get_db

load_dotenv()

logger = logging.getLogger("synapse.auth")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# =====================================================================
# Cryptographic & JWT Configuration
# =====================================================================

# Load secret key from environment or use a secure 64-character default
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "synapse_ai_secure_jwt_secret_key_2026_production_grade_crypto_seed_64bytes"
).strip()

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# HTTP Bearer scheme for token extraction
security_scheme = HTTPBearer(auto_error=False)


# =====================================================================
# Password Hashing & Validation
# =====================================================================

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password securely using bcrypt with a salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed_bytes = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.warning("Password verification failed with error: %s", str(e))
        return False


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password complexity and length requirements.
    Must be at least 8 characters long.
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password cannot exceed 128 characters."
    return True, None


def validate_email_format(email: str) -> bool:
    """Validate RFC-compliant email structure."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))


# =====================================================================
# JWT Token Generation & Verification
# =====================================================================

def create_access_token(
    user_id: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a signed JWT access token with expiration and user claims.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "email": email.lower().strip(),
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a signed JWT token.
    Raises HTTPException(401) on expiration, tampering, or invalid claims.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is missing required subject claim ('sub').",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =====================================================================
# Current User Resolution Dependency
# =====================================================================

def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that resolves the authenticated user from the Bearer JWT token.
    Raises 401 if credentials are missing, invalid, or expired.
    """
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth_header.credentials)
    user_id = payload.get("sub")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user account has been deactivated.",
        )

    return user


def get_optional_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    FastAPI dependency that returns the current User if valid Bearer token provided,
    or None if unauthenticated (for public endpoints).
    """
    if not auth_header or not auth_header.credentials:
        return None
    try:
        payload = decode_access_token(auth_header.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    except Exception:
        return None


# =====================================================================
# Backend Authorization & Ownership Verification
# =====================================================================

def verify_project_ownership(project: Optional[ResearchProject], user: User) -> None:
    """
    Strictly verify that the requesting user owns the research project.
    Raises 404 if project is missing, or 403 Forbidden if owned by another user.
    """
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research project not found.",
        )
    if project.user_id != user.id:
        logger.warning(
            "Access violation: User %s attempted to access Project %s owned by %s",
            user.id, project.id, project.user_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this research project.",
        )


def verify_session_ownership(session: Optional[ResearchSession], user: User) -> None:
    """
    Strictly verify that the requesting user owns the research session via its parent project.
    Raises 404 if session is missing, or 403 Forbidden if owned by another user.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found.",
        )
    if not session.project or session.project.user_id != user.id:
        logger.warning(
            "Access violation: User %s attempted to access Session %s in Project owned by %s",
            user.id, session.id, getattr(session.project, "user_id", "unknown")
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this research session.",
        )


def verify_report_ownership(report: Optional[Report], user: User) -> None:
    """
    Strictly verify that the requesting user owns the research report via parent session and project.
    """
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )
    if not report.session or not report.session.project or report.session.project.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this report.",
        )


# =====================================================================
# Registration & Authentication Services
# =====================================================================

def register_user(
    db: Session,
    email: str,
    password: str,
    username: Optional[str] = None,
    full_name: Optional[str] = None
) -> User:
    """Register a new user with hashed password validation."""
    clean_email = email.lower().strip()

    if not validate_email_format(clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format.",
        )

    is_valid, msg = validate_password_strength(password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # Check for existing email
    existing = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = User(
        id=generate_uuid(),
        email=clean_email,
        username=username.strip() if username else clean_email.split("@")[0],
        full_name=full_name.strip() if full_name else None,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create default workspace project for this new user
    from db.service import create_project
    create_project(
        db=db,
        user_id=user.id,
        title="Personal Research Workspace",
        description="Default workspace for autonomous research sessions."
    )

    logger.info("Successfully registered user: %s (id: %s)", user.email, user.id)
    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str
) -> User:
    """Verify credentials and return authenticated user."""
    clean_email = email.lower().strip()
    user = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()

    if not user or not user.hashed_password:
        logger.warning("Failed login attempt for email: %s", clean_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.hashed_password):
        logger.warning("Incorrect password for email: %s", clean_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support.",
        )

    logger.info("User successfully authenticated: %s", user.email)
    return user
