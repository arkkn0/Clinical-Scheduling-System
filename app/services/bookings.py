from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Booking, BookingEvent, Patient, Slot
from app.schemas import BookingCreate


@dataclass(frozen=True)
class BookingResult:
    booking: Booking
    replayed: bool


def _replay_or_reject(existing: Booking, payload: BookingCreate) -> BookingResult:
    if existing.patient_id != payload.patient_id or existing.slot_id != payload.slot_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key was already used for a different booking request",
        )
    return BookingResult(booking=existing, replayed=True)


def book_slot(
    payload: BookingCreate,
    db: Session,
    *,
    idempotency_key: str | None = None,
) -> BookingResult:
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

        # The slot lock also serialises retries for this slot. Re-read the key
        # after acquiring it so a waiting request can observe the committed result.
        if idempotency_key is not None:
            prior = db.execute(
                select(Booking).where(Booking.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if prior is not None:
                return _replay_or_reject(prior, payload)

        existing = db.execute(
            select(Booking).where(Booking.slot_id == payload.slot_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slot is already booked",
            )

        booking = Booking(
            patient_id=payload.patient_id,
            slot_id=payload.slot_id,
            idempotency_key=idempotency_key,
        )
        db.add(booking)
        db.flush()
        db.add(
            BookingEvent(
                booking_id=booking.id,
                event_type="booked",
                patient_id=booking.patient_id,
                slot_id=booking.slot_id,
                idempotency_key=idempotency_key,
            )
        )
        db.commit()
        db.refresh(booking)
        return BookingResult(booking=booking, replayed=False)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        # The UNIQUE constraint remains the final guard if a caller bypasses
        # the row-locking path or a future refactor weakens it.
        db.rollback()
        if idempotency_key is not None:
            prior = db.execute(
                select(Booking).where(Booking.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if prior is not None:
                return _replay_or_reject(prior, payload)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot is already booked",
        ) from None
