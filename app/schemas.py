from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    name: str
    email: str


class PatientOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorCreate(BaseModel):
    name: str
    specialty: str


class DoctorOut(BaseModel):
    id: int
    name: str
    specialty: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SlotCreate(BaseModel):
    doctor_id: int
    start_time: datetime
    end_time: datetime


class SlotOut(BaseModel):
    id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    patient_id: int
    slot_id: int


class BookingOut(BaseModel):
    id: int
    patient_id: int
    slot_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
