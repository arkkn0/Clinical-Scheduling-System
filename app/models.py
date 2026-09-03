from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    specialty = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True)
    doctor_id = Column(
        Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("slot_id", name="uq_bookings_slot_id"),)

    id = Column(Integer, primary_key=True)
    patient_id = Column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_id = Column(Integer, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BookingEvent(Base):
    __tablename__ = "booking_events"

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(32), nullable=False)
    patient_id = Column(Integer, nullable=False)
    slot_id = Column(Integer, nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
