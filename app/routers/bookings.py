from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Booking, BookingEvent
from app.schemas import BookingCreate, BookingOut
from app.services.bookings import book_slot

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    response: Response,
    db: Session = Depends(get_db),
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ] = None,
):
    result = book_slot(payload, db, idempotency_key=idempotency_key)
    response.headers["Idempotency-Replayed"] = str(result.replayed).lower()
    return result.booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    db.add(
        BookingEvent(
            booking_id=booking.id,
            event_type="cancelled",
            patient_id=booking.patient_id,
            slot_id=booking.slot_id,
            idempotency_key=booking.idempotency_key,
        )
    )
    db.delete(booking)
    db.commit()
