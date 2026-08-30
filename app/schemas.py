from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class PatientCreate(BaseModel):
    name: Name
    email: EmailStr


class PatientOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorCreate(BaseModel):
    name: Name
    specialty: Name


class DoctorOut(BaseModel):
    id: int
    name: str
    specialty: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SlotCreate(BaseModel):
    doctor_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone offset is required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_interval(self) -> "SlotCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        return self


class SlotOut(BaseModel):
    id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    patient_id: int = Field(gt=0)
    slot_id: int = Field(gt=0)


class BookingOut(BaseModel):
    id: int
    patient_id: int
    slot_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
