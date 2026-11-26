from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.user import User
from app.services.auth_service import AuthService
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedException, ForbiddenException

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency to extract and validate the authenticated user."""
    user_id_str = decode_access_token(token)
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise UnauthorizedException("Malformed user identifier in token")

    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise UnauthorizedException("Inactive user account")
    return user


def require_roles(*allowed_roles: str):
    """Dependency factory enforcing role-based authorization (RBAC)."""
    async def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user
        user_role = getattr(current_user, "role", "student")
        if user_role not in allowed_roles:
            raise ForbiddenException(f"Insufficient permissions: requires role in {list(allowed_roles)}")
        return current_user

    return _role_checker
