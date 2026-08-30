from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import availability, bookings, doctors, patients, slots


def create_app() -> FastAPI:
    application = FastAPI(
        title="Clinical Scheduling System",
        version="2.0.0",
        description="Conflict-safe appointment scheduling API.",
    )
    application.include_router(patients.router)
    application.include_router(doctors.router)
    application.include_router(slots.router)
    application.include_router(availability.router)
    application.include_router(bookings.router)
    return application


app = create_app()


@app.get("/health", tags=["health"], summary="Liveness probe")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["health"], summary="Database readiness probe")
def readiness_check(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "ready"}
