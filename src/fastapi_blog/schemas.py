from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    pass


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

    @field_validator("service_date")
    @classmethod
    def date_not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("service_date cannot be in the future")
        return value


class RecordResponse(RecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    owner: UserResponse
