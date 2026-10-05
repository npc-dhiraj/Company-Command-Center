from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.storage.models.user import UserRole


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=12)
    role: UserRole = UserRole.MEMBER


class UserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
