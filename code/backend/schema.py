from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

INSPECTION_CODE_PATTERN = r"^INS-\d{5}$"
PHONE_PATTERN = r"^\d{3}-\d{3}-\d{4}$"


# ----- owners -----
class OwnerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(pattern=PHONE_PATTERN)
    email: EmailStr


class OwnerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    email: Optional[EmailStr] = None


class OwnerOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    createdAt: datetime
    updatedAt: datetime


# ----- inspections -----
class InspectionCreate(BaseModel):
    restaurantName: str = Field(min_length=1, max_length=255)
    cuisine: str = Field(min_length=1, max_length=255)
    inspectionCode: str = Field(pattern=INSPECTION_CODE_PATTERN)
    score: int = Field(default=100, ge=0, le=100)
    ownerId: int = Field(gt=0)


class InspectionUpdate(BaseModel):
    restaurantName: Optional[str] = Field(default=None, min_length=1, max_length=255)
    cuisine: Optional[str] = Field(default=None, min_length=1, max_length=255)
    inspectionCode: Optional[str] = Field(default=None, pattern=INSPECTION_CODE_PATTERN)
    score: Optional[int] = Field(default=None, ge=0, le=100)
    ownerId: Optional[int] = Field(default=None, gt=0)


class InspectionOut(BaseModel):
    id: int
    restaurantName: str
    cuisine: str
    inspectionCode: str
    score: int
    ownerId: int
    createdAt: datetime
    updatedAt: datetime


class ViolationOut(BaseModel):
    id: int
    description: str
    severity: str


class InspectionWithViolations(InspectionOut):
    violations: list[ViolationOut]


class Token(BaseModel):
    access_token: str
    token_type: str


class AuthMeOut(BaseModel):
    id: int
    username: str
    name: str
    role: str


class LoginIn(BaseModel):
    """Kept for older clients; HW7 login uses OAuth2 form username/password."""

    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
