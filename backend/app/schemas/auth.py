import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    tenant_name: str = Field(..., min_length=1, max_length=255)
    tenant_slug: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=12)

    @field_validator("tenant_slug")
    @classmethod
    def validate_tenant_slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError(
                "Tenant slug must contain only lowercase letters, digits, and hyphens"
            )
        return v


class LoginRequest(BaseModel):
    tenant_slug: str
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
