from datetime import date
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


def not_in_future(value: date) -> date:
    if value > date.today():
        raise ValueError("service_date cannot be in the future")
    return value


PastDate = Annotated[date, AfterValidator(not_in_future)]


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = None

    @field_validator("username", "email")
    @classmethod
    def not_null_when_provided(cls, value):
        if value is None:
            raise ValueError("field cannot be null")
        return value


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RecordBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    notes: str = Field(default="", max_length=1000)
    mileage_km: int = Field(ge=0)
    service_date: date


class RecordCreate(RecordBase):
    user_id: int  # temporary until authentication (class 11)
    service_date: PastDate


class RecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=1000)
    mileage_km: int | None = Field(default=None, ge=0)
    service_date: PastDate | None = None

    @field_validator("title", "notes", "mileage_km", "service_date")
    @classmethod
    def not_null_when_provided(cls, value):
        if value is None:
            raise ValueError("field cannot be null")
        return value


class RecordResponse(RecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    owner: UserResponse
