from fastapi import FastAPI

from app.database import Base, engine
from app.routers import availability, bookings, doctors, patients, slots


app = FastAPI(title="Clinical Scheduling System", version="1.0.0")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(slots.router)
app.include_router(availability.router)
app.include_router(bookings.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
