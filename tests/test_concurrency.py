import asyncio

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Booking


@pytest.mark.mysql
@pytest.mark.anyio
async def test_fifty_competing_requests_create_exactly_one_booking(
    client: TestClient,
    db_engine: Engine,
    seeded_ids: dict[str, int],
) -> None:
    if db_engine.dialect.name != "mysql":
        pytest.skip("row-locking guarantee requires MySQL")

    payload = {
        "patient_id": seeded_ids["patient_id"],
        "slot_id": seeded_ids["slot_id"],
    }

    transport = ASGITransport(app=client.app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        responses = await asyncio.gather(
            *(async_client.post("/bookings", json=payload) for _ in range(50))
        )
    statuses = [response.status_code for response in responses]

    with Session(db_engine) as session:
        booking_count = session.scalar(select(func.count()).select_from(Booking))

    assert statuses.count(201) == 1
    assert statuses.count(409) == 49
    assert booking_count == 1
