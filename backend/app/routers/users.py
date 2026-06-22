from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models, schemas, auth
from app.limiter import limiter
from fastapi import Request
from datetime import datetime, timezone, timedelta
from app.email import generate_verification_token, verification_token_expiry, send_verification_email

router = APIRouter(prefix="/api/users")

@router.post("/register", response_model=schemas.UserOut)
@limiter.limit("5/minute")
async def register(request: Request, user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(models.User).where(
            (models.User.email == user.email) | (models.User.username == user.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email or username already taken")
    token = generate_verification_token()
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=auth.hash_password(user.password),
        is_verified=False,
        verification_token=token,
        verification_token_expires=verification_token_expiry()
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    await send_verification_email(user.email, user.username, token)
    return db_user

@router.post("/login", response_model=schemas.Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(models.User).where(models.User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    # Check if account is locked
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds()/60)
        raise HTTPException(status_code=403, detail=f"Account locked. Try again in {remaining} minutes.")

    # Check password
    if not auth.verify_password(form_data.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            user.failed_login_attempts = 0
            await db.commit()
            raise HTTPException(status_code=403, detail="Too many failed attempts. Account locked for 15 minutes.")
        await db.commit()
        raise HTTPException(status_code=401, detail=f"Incorrect email or password. {5-user.failed_login_attempts} attempts remaining.")

    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    token = auth.create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserOut)
async def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(models.User).where(models.User.verification_token == token))
        user = result.scalar_one_or_none()
        if not user:
                raise HTTPException(400, "Invalid verification token")
        if user.verification_token_expires < datetime.now(timezone.utc):
                raise HTTPException(400, "Verification token expired")
        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        await db.commit()
        return {"ok": True}

@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(request: Request, email: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(models.User).where(models.User.email == email))
        user = result.scalar_one_or_none()
        if not user or user.is_verified:
                return {"ok":True} # Don't reveal if email exists
        token = generate_verification_token()
        user.verification_token = token
        user.verification_token_expires = verification_token_expiry()
        await db.commit()
        await send_verification_email(user.email, user.username, token)
        return {"ok": True}
