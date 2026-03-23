# 🏥 Clinical Scheduling System

A backend scheduling system built with **FastAPI** and **MySQL**, designed to handle concurrent appointment booking requests with zero double-booking. Containerised with Docker and deployment-ready for AWS EC2 + RDS.

---

## 📌 Project Overview

This system provides a RESTful API backend for managing clinical appointments — including doctor availability, patient registration, slot management, and conflict-safe bookings.

The core engineering challenge is **concurrency**: when multiple patients attempt to book the same slot simultaneously, the system must guarantee that only one booking succeeds. This is solved using **MySQL row-level locking (`SELECT ... FOR UPDATE`)** inside a transaction, backed by a **UNIQUE constraint** as a second safety net.

> ⚠️ This is a backend-only MVP. No authentication, frontend, or advanced scheduling logic is included by design.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11 |
| Framework | FastAPI |
| Database | MySQL 8.0 |
| ORM | SQLAlchemy 2.0 |
| Containerisation | Docker + Docker Compose |
| Deployment Target | AWS EC2 + RDS (designed) |
| API Docs | Swagger UI (auto-generated) |

---

## 🏗️ System Architecture

```
Client (HTTP)
     │
     ▼
┌─────────────────────────┐
│  FastAPI Application    │
│  Uvicorn (4 workers)    │
│  Routers: 6 endpoints   │
└───────────┬─────────────┘
            │ SQLAlchemy ORM
            ▼
┌─────────────────────────┐
│  MySQL 8.0              │
│  Tables: 4              │
│  - patients             │
│  - doctors              │
│  - slots                │
│  - bookings             │
└─────────────────────────┘
```

**Docker Compose** runs both the app and MySQL as separate services, linked on an internal network.

---

## 📋 Database Schema

```
patients        doctors
────────        ───────
id (PK)         id (PK)
name            name
email (unique)  specialty

slots                    bookings
─────                    ────────
id (PK)                  id (PK)
doctor_id (FK)           slot_id (FK, UNIQUE)  ← conflict guard
start_time               patient_id (FK)
end_time
```

The `UNIQUE` constraint on `bookings.slot_id` ensures one slot can only ever have one booking at the database level.

---

## 🔌 API Reference

| # | Method | Endpoint | Description |
|---|--------|----------|-------------|
| 1 | POST | `/doctors` | Register a new doctor |
| 2 | POST | `/patients` | Register a new patient |
| 3 | POST | `/slots` | Create an available time slot |
| 4 | GET | `/availability` | List all unbooked slots |
| 5 | POST | `/bookings` | Book a slot (concurrency-safe) |
| 6 | DELETE | `/bookings/{booking_id}` | Cancel a booking |

Interactive docs available at: `http://localhost:8000/docs`

---

## 🔒 Key Feature: Transactional Conflict-Checking

**Problem:** Without protection, two concurrent requests can both read a slot as "available" and both insert a booking — creating a double booking.

**Solution — two-layer defence:**

### Layer 1: Row-Level Lock (`SELECT ... FOR UPDATE`)
```python
slot = (
    db.query(Slot)
    .filter(Slot.id == payload.slot_id)
    .with_for_update()   # locks this row in MySQL
    .first()
)
```
When a booking request arrives, the app locks the target slot row. Any concurrent transaction trying to access the same row is **blocked** until the first one commits or rolls back. This eliminates the read-then-write race condition.

### Layer 2: UNIQUE Constraint
```sql
UNIQUE KEY uq_booking_slot (slot_id)
```
Even if row locking is bypassed (e.g. misconfigured connection pool), MySQL will reject a duplicate `INSERT` with an `IntegrityError`, which the app converts to a `409 Conflict` response.

**Result:** Exactly one booking succeeds. All others receive `409 Slot already booked`.

---

## 🧪 Concurrency Test: 50 Simultaneous Requests

A test script fires **50 concurrent threads**, each attempting to book the same slot at the same time.

```bash
python tests/test_concurrency.py
```

**Result:**
```
========================================
CONCURRENCY TEST RESULTS
========================================
Total requests   : 50
Success (201)    : 1
Failed  (409/4xx): 49
Errors  (timeout): 0
Double bookings  : 0
========================================
✅ PASSED — conflict prevention works correctly
```

This directly supports the claim:
> *"Reducing double-booking to 0% under 50+ concurrent requests"*

---

## 🚀 Run Locally

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/clinical-scheduling.git
cd clinical-scheduling

# 2. Start the app + MySQL
docker compose up --build

# 3. Wait ~30 seconds, then verify
# Open browser: http://localhost:8000/health
# → {"status": "ok"}
```

Tables are created automatically on first startup.

---

## 📡 Example API Usage

### Create a doctor
```bash
curl -X POST http://localhost:8000/doctors \
  -H "Content-Type: application/json" \
  -d '{"name": "Dr. Smith", "specialty": "Cardiology"}'
```

### Create a patient
```bash
curl -X POST http://localhost:8000/patients \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com"}'
```

### Create a slot
```bash
curl -X POST http://localhost:8000/slots \
  -H "Content-Type: application/json" \
  -d '{"doctor_id": 1, "start_time": "2025-09-01T09:00:00", "end_time": "2025-09-01T09:30:00"}'
```

### Book a slot
```bash
curl -X POST http://localhost:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{"slot_id": 1, "patient_id": 1}'
```

### Try to double-book (expect 409)
```bash
curl -X POST http://localhost:8000/bookings \
  -H "Content-Type: application/json" \
  -d '{"slot_id": 1, "patient_id": 1}'
# → {"detail": "Slot already booked"}
```

### Cancel a booking
```bash
curl -X DELETE http://localhost:8000/bookings/1
```

---

## ☁️ AWS Deployment Design

> Deployment was designed but not provisioned — the resume states "designed deployment", which this section documents.

```
Internet
    │
    ▼
[EC2 t3.small — Amazon Linux 2023]
  Docker container
  uvicorn --workers 4
    │
    │ private subnet (port 3306 only)
    ▼
[RDS MySQL 8.0 — db.t3.micro]
```

### Deployment Steps (~5 min)

1. **RDS** — Launch MySQL 8.0 `db.t3.micro` in a private subnet. Note the endpoint URL.
2. **EC2** — Launch `t3.small`, install Docker:
   ```bash
   sudo yum install docker -y && sudo service docker start
   ```
3. **Deploy:**
   ```bash
   git clone <repo> && cd clinical-scheduling
   DATABASE_URL=mysql+pymysql://root:<pw>@<rds-endpoint>:3306/clinical \
   docker compose up --build -d
   ```
4. **Security groups:**
   - EC2 inbound: port `8000` open to `0.0.0.0/0`
   - RDS inbound: port `3306` open to EC2 security group only

### Why setup time drops from ~20 min to <5 min

Without Docker, you would manually install Python, pip packages, and configure MySQL on every new server — error-prone and slow (~20 min). With this Docker setup, the entire environment is reproduced with **one command** in under 5 minutes.

---

## 📁 Project Structure

```
clinical-scheduling/
├── app/
│   ├── main.py              # App entry point, router registration
│   ├── database.py          # SQLAlchemy engine + session
│   ├── models.py            # ORM models (4 tables)
│   ├── schemas.py           # Pydantic request/response schemas
│   └── routers/
│       ├── patients.py      # POST /patients
│       ├── doctors.py       # POST /doctors
│       ├── slots.py         # POST /slots
│       ├── availability.py  # GET /availability
│       └── bookings.py      # POST /bookings, DELETE /bookings/{id}
├── tests/
│   └── test_concurrency.py  # 50-thread concurrent booking test
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🏆 Key Achievements

| Metric | Detail |
|--------|--------|
| Double bookings under 50 concurrent requests | **0** |
| REST API endpoints | **6** |
| Docker setup time | **< 5 min** (vs ~20 min manual) |
| Workers | **4** Uvicorn workers |
| Database conflict layers | **2** (row lock + unique constraint) |

---

## 📄 License

MIT
