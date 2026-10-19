from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

StatusEnum = Literal["open", "closed", "follow_up"]
CuisineEnum = Literal["American", "Chinese", "Italian", "Japanese", "Mexican", "Indian", "Thai", "Other"]
SeverityEnum = Literal["critical", "major", "minor"]


class OwnerDoc(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)


class ViolationDoc(BaseModel):
    description: str = Field(..., min_length=1, max_length=300)
    severity: SeverityEnum


class InspectionDocCreate(BaseModel):
    restaurantName: str = Field(..., min_length=1, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)
    status: StatusEnum = "open"
    cuisine: CuisineEnum
    inspectedAt: datetime
    score: int = Field(100, ge=0, le=100)
    owner: Optional[OwnerDoc] = None
    violations: list[ViolationDoc] = []


class InspectionDocUpdate(BaseModel):
    restaurantName: Optional[str] = Field(None, min_length=1, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[StatusEnum] = None
    cuisine: Optional[CuisineEnum] = None
    inspectedAt: Optional[datetime] = None
    score: Optional[int] = Field(None, ge=0, le=100)
    owner: Optional[OwnerDoc] = None
    violations: Optional[list[ViolationDoc]] = None


class InspectionDocOut(BaseModel):
    id: str
    restaurantName: str
    notes: Optional[str] = None
    status: StatusEnum
    cuisine: CuisineEnum
    inspectedAt: datetime
    score: int
    owner: Optional[OwnerDoc] = None
    violations: list[ViolationDoc] = []
    createdAt: datetime
    updatedAt: datetime


class ChatIn(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    session_id: Optional[str] = Field(None, max_length=80)
    message: str = Field(..., min_length=1, max_length=4000)
    short_term_n: Optional[int] = Field(None, ge=1, le=100)
    policy: Literal["none", "compress"] = "none"
    run_label: str = Field("live", max_length=40)
    phase: str = Field("live", max_length=40)
