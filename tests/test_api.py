from fastapi.testclient import TestClient


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_booking_lifecycle_updates_availability(
    client: TestClient,
    seeded_ids: dict[str, int],
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
