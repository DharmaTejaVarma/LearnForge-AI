from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserUpdate, Token, UserResponse
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.exceptions import ConflictException, UnauthorizedException, NotFoundException
from app.core.logging import logger

class AuthService:
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    @staticmethod
    async def register_user(db: AsyncSession, user_in: UserCreate) -> Token:
        existing = await AuthService.get_user_by_email(db, user_in.email)
        if existing:
            raise ConflictException(f"User with email '{user_in.email}' already exists")

        user = User(
            email=user_in.email,
            hashed_password=get_password_hash(user_in.password),
            full_name=user_in.full_name,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Registered new user: {user.email} (id={user.id})")
        token = create_access_token(subject=str(user.id))
        return Token(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def authenticate_user(db: AsyncSession, credentials: UserLogin) -> Token:
        user = await AuthService.get_user_by_email(db, credentials.email)
        if not user or not verify_password(credentials.password, user.hashed_password):
            raise UnauthorizedException("Incorrect email or password")

        if not user.is_active:
            raise UnauthorizedException("User account is inactive")

        logger.info(f"Authenticated user: {user.email} (id={user.id})")
        token = create_access_token(subject=str(user.id))
        return Token(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def update_user(db: AsyncSession, user_id: int, user_update: UserUpdate) -> UserResponse:
        user = await AuthService.get_user_by_id(db, user_id)
        if not user:
            raise NotFoundException("User not found")

        if user_update.full_name is not None:
            user.full_name = user_update.full_name
        if user_update.password:
            user.hashed_password = get_password_hash(user_update.password)

        await db.commit()
        await db.refresh(user)
        return UserResponse.model_validate(user)
