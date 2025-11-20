import uuid

from fastapi_users import schemas
from pydantic import field_validator

from app.utils.password_validator import validate_password


class UserRead(schemas.BaseUser[uuid.UUID]):
    pages_limit: int
    pages_used: int


class UserCreate(schemas.BaseUserCreate):
    """
    User creation schema with password validation.

    Password Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character
    - Cannot be a commonly used weak password
    """

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets complexity requirements."""
        from app.utils.password_validator import PasswordValidationError

        try:
            return validate_password(v)
        except PasswordValidationError as e:
            # Re-raise as ValueError for Pydantic
            raise ValueError(str(e)) from e


class UserUpdate(schemas.BaseUserUpdate):
    """
    User update schema with optional password validation.

    If password is being updated, it must meet the same requirements as registration.
    """

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str | None) -> str | None:
        """Validate password meets complexity requirements if provided."""
        if v is None:
            return v

        from app.utils.password_validator import PasswordValidationError

        try:
            return validate_password(v)
        except PasswordValidationError as e:
            # Re-raise as ValueError for Pydantic
            raise ValueError(str(e)) from e
