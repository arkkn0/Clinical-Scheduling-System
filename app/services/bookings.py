from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Booking, Patient, Slot
from app.schemas import BookingCreate


def book_slot(payload: BookingCreate, db: Session) -> Booking:
    """Create one booking while preserving the one-booking-per-slot invariant."""
    patient = db.get(Patient, payload.patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    try:
        # The slot is the shared resource. Locking it serialises competing
        # bookings before the read-then-insert sequence.
        slot = db.execute(
            select(Slot)
            .where(Slot.id == payload.slot_id, Slot.is_active.is_(True))
            .with_for_update()
        ).scalar_one_or_none()
        if slot is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")

        existing = db.execute(
            select(Booking.id).where(Booking.slot_id == payload.slot_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slot is already booked",
            )

        booking = Booking(patient_id=payload.patient_id, slot_id=payload.slot_id)
        db.add(booking)
        db.commit()
        db.refresh(booking)
        return booking
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        # The UNIQUE constraint remains the final guard if a caller bypasses
        # the row-locking path or a future refactor weakens it.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot is already booked",
        ) from None
