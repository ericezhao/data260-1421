from pydantic import BaseModel, Field


class InspectionCreate(BaseModel):
    restaurantName: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)


class InspectionUpdate(BaseModel):
    restaurantName: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)


class InspectionOut(BaseModel):
    id: int
    restaurantName: str
    cuisine: str


class ViolationOut(BaseModel):
    id: int
    description: str
    severity: str


class InspectionWithViolations(InspectionOut):
    violations: list[ViolationOut]


class LoginIn(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
