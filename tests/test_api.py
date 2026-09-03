from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Booking, BookingEvent


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_booking_lifecycle_updates_availability(
    client: TestClient,
    seeded_ids: dict[str, int],
    session_factory: sessionmaker[Session],
) -> None:
    slot_id = seeded_ids["slot_id"]
    booking = client.post(
        "/bookings",
        json={"patient_id": seeded_ids["patient_id"], "slot_id": slot_id},
    )

    assert booking.status_code == 201
    assert client.get("/availability").json() == []

    duplicate = client.post(
        "/bookings",
        json={"patient_id": seeded_ids["patient_id"], "slot_id": slot_id},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Slot is already booked"}

    cancelled = client.delete(f"/bookings/{booking.json()['id']}")
    assert cancelled.status_code == 204
    assert [item["id"] for item in client.get("/availability").json()] == [slot_id]

    with session_factory() as session:
        events = session.scalars(
            select(BookingEvent).order_by(BookingEvent.id)
        ).all()
    assert [(event.booking_id, event.event_type) for event in events] == [
        (booking.json()["id"], "booked"),
        (booking.json()["id"], "cancelled"),
    ]


def test_idempotency_key_replays_the_original_booking(
    client: TestClient,
    seeded_ids: dict[str, int],
    session_factory: sessionmaker[Session],
) -> None:
    payload = {
        "patient_id": seeded_ids["patient_id"],
        "slot_id": seeded_ids["slot_id"],
    }
    headers = {"Idempotency-Key": "booking-request-001"}

    first = client.post("/bookings", json=payload, headers=headers)
    replay = client.post("/bookings", json=payload, headers=headers)

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert first.headers["Idempotency-Replayed"] == "false"
    assert replay.headers["Idempotency-Replayed"] == "true"
    with session_factory() as session:
        assert len(session.scalars(select(Booking)).all()) == 1
        assert len(session.scalars(select(BookingEvent)).all()) == 1


def test_idempotency_key_cannot_be_reused_for_different_payload(
    client: TestClient,
    seeded_ids: dict[str, int],
) -> None:
    headers = {"Idempotency-Key": "booking-request-002"}
    first = client.post(
        "/bookings",
        json={
            "patient_id": seeded_ids["patient_id"],
            "slot_id": seeded_ids["slot_id"],
        },
        headers=headers,
    )
    other_patient = client.post(
        "/patients", json={"name": "Alan Turing", "email": "alan@example.com"}
    )
    conflict = client.post(
        "/bookings",
        json={
            "patient_id": other_patient.json()["id"],
            "slot_id": seeded_ids["slot_id"],
        },
        headers=headers,
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "Idempotency key was already used for a different booking request"
    }


def test_rejects_overlapping_slots_for_same_doctor(
    client: TestClient,
    seeded_ids: dict[str, int],
) -> None:
    response = client.post(
        "/slots",
        json={
            "doctor_id": seeded_ids["doctor_id"],
            "start_time": "2030-01-01T09:15:00Z",
            "end_time": "2030-01-01T09:45:00Z",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Slot overlaps an existing active slot"}


def test_allows_touching_non_overlapping_slots(
    client: TestClient,
    seeded_ids: dict[str, int],
) -> None:
    response = client.post(
        "/slots",
        json={
            "doctor_id": seeded_ids["doctor_id"],
            "start_time": "2030-01-01T09:30:00Z",
            "end_time": "2030-01-01T10:00:00Z",
        },
    )
    assert response.status_code == 201


def test_validates_timezones_and_interval_order(client: TestClient) -> None:
    doctor = client.post(
        "/doctors",
        json={"name": "Dr. Turing", "specialty": "Neurology"},
    ).json()

    missing_timezone = client.post(
        "/slots",
        json={
            "doctor_id": doctor["id"],
            "start_time": "2030-01-01T09:00:00",
            "end_time": "2030-01-01T09:30:00",
        },
    )
    reversed_interval = client.post(
        "/slots",
        json={
            "doctor_id": doctor["id"],
            "start_time": "2030-01-01T10:00:00Z",
            "end_time": "2030-01-01T09:30:00Z",
        },
    )

    assert missing_timezone.status_code == 422
    assert reversed_interval.status_code == 422


def test_normalises_and_deduplicates_patient_email(client: TestClient) -> None:
    first = client.post(
        "/patients",
        json={"name": "  Katherine Johnson  ", "email": "Katherine@example.com"},
    )
    duplicate = client.post(
        "/patients",
        json={"name": "Katherine Johnson", "email": "Katherine@example.com"},
    )

    assert first.status_code == 201
    assert first.json()["name"] == "Katherine Johnson"
    assert duplicate.status_code == 409
