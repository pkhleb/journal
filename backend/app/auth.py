from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models
import os

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")

def verify_password(plain, hashed):
    """Verify a plaintext password against a stored bcrypt hash.

    Args:
        plain: The raw password submitted by the user.
        hashed: The stored password hash to compare against.

    Returns:
        bool: True if the password matches the hash; otherwise False.
    """
    return pwd_context.verify(plain, hashed)

def hash_password(password):
    """Hash a plaintext password using the configured bcrypt scheme.

    Args:
        password: The plaintext password to hash.

    Returns:
        str: A bcrypt hash suitable for storage.
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token for a given user payload.

    Args:
        data: Arbitrary JWT payload data.
        expires_delta: Optional custom expiry window. Defaults to 30 days.

    Returns:
        str: The encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Resolve the authenticated user from a bearer token.

    Args:
        token: The bearer token submitted in the Authorization header.
        db: Active database session used to load the user record.

    Raises:
        HTTPException: If the token is invalid or the user no longer exists.

    Returns:
        models.User: The authenticated user model.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
