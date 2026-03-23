from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Booking, Slot
from app.schemas import SlotOut


router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=list[SlotOut])
def list_available_slots(doctor_id: int | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(Slot)
        .outerjoin(Booking, Booking.slot_id == Slot.id)
        .where(Slot.is_active.is_(True))
        .where(Slot.start_time >= datetime.utcnow())
        .where(Booking.id.is_(None))
        .order_by(Slot.start_time.asc())
    )
    if doctor_id is not None:
        stmt = stmt.where(Slot.doctor_id == doctor_id)
    return db.execute(stmt).scalars().all()
