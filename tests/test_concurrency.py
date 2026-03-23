from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


BASE_URL = "http://127.0.0.1:8000"
THREADS = 50


def seed_data():
    doctor_resp = requests.post(
        f"{BASE_URL}/doctors",
        json={"name": "Dr. Concurrency", "specialty": "General Medicine"},
        timeout=10,
    )
    doctor_resp.raise_for_status()
    doctor_id = doctor_resp.json()["id"]

    patient_resp = requests.post(
        f"{BASE_URL}/patients",
        json={"name": "Test Patient", "email": "patient_concurrency@example.com"},
        timeout=10,
    )
    patient_resp.raise_for_status()
    patient_id = patient_resp.json()["id"]

    slot_resp = requests.post(
        f"{BASE_URL}/slots",
        json={
            "doctor_id": doctor_id,
            "start_time": "2030-01-01T09:00:00Z",
            "end_time": "2030-01-01T09:30:00Z",
        },
        timeout=10,
    )
    slot_resp.raise_for_status()
    slot_id = slot_resp.json()["id"]

    return patient_id, slot_id


def book_once(patient_id: int, slot_id: int) -> int:
    resp = requests.post(
        f"{BASE_URL}/bookings",
        json={"patient_id": patient_id, "slot_id": slot_id},
        timeout=10,
    )
    return resp.status_code


def main():
    patient_id, slot_id = seed_data()
    success = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(book_once, patient_id, slot_id) for _ in range(THREADS)]
        for future in as_completed(futures):
            status_code = future.result()
            if status_code == 201:
                success += 1
            else:
                failed += 1

    availability_resp = requests.get(f"{BASE_URL}/availability", timeout=10)
    availability_resp.raise_for_status()
    available_slots = availability_resp.json()
    double_booking_count = 0 if len(available_slots) == 0 else len(available_slots) - 1

    print(f"Total requests: {THREADS}")
    print(f"Success count: {success}")
    print(f"Failed count: {failed}")
    print(f"Double booking count: {double_booking_count}")


if __name__ == "__main__":
    main()
