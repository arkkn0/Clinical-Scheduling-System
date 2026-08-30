import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
def db_engine() -> Generator[Engine, None, None]:
    database_url = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    engine_options: dict[str, object] = {"future": True, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_options.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    engine = create_engine(database_url, **engine_options)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def session_factory(db_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_ids(client: TestClient) -> dict[str, int]:
    doctor = client.post(
        "/doctors",
        json={"name": "Dr. Ada", "specialty": "General Medicine"},
    )
    patient = client.post(
        "/patients",
        json={"name": "Grace Hopper", "email": "grace@example.com"},
    )
    slot = client.post(
        "/slots",
        json={
            "doctor_id": doctor.json()["id"],
            "start_time": "2030-01-01T09:00:00Z",
            "end_time": "2030-01-01T09:30:00Z",
        },
    )
    assert doctor.status_code == patient.status_code == slot.status_code == 201
    return {
        "doctor_id": doctor.json()["id"],
        "patient_id": patient.json()["id"],
        "slot_id": slot.json()["id"],
    }
