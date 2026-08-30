from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Doctor, Slot
from app.schemas import SlotCreate, SlotOut

router = APIRouter(prefix="/slots", tags=["slots"])


@router.post("", response_model=SlotOut, status_code=status.HTTP_201_CREATED)
def create_slot(payload: SlotCreate, db: Session = Depends(get_db)):
    # Serialise slot creation per doctor so overlapping ranges cannot race past
    # the application-level interval check.
    doctor = db.execute(
        select(Doctor).where(Doctor.id == payload.doctor_id).with_for_update()
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    overlap = db.execute(
        select(Slot.id).where(
            Slot.doctor_id == payload.doctor_id,
            Slot.is_active.is_(True),
            Slot.start_time < payload.end_time,
            Slot.end_time > payload.start_time,
        )
    ).scalar_one_or_none()
    if overlap is not None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot overlaps an existing active slot",
        )
    slot = Slot(
        doctor_id=payload.doctor_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_active=True,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot
