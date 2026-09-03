# Clinical Scheduling System

A small FastAPI and MySQL service built around one deceptively hard requirement: two patients must never own the same appointment slot, even when requests arrive together.

The project stays backend-only so the interesting parts remain visible: transaction boundaries, database constraints, interval conflicts, failure responses, migrations, and reproducible tests.

## What it guarantees

- One booking per slot. The booking transaction locks the slot row before it checks and writes; a unique constraint on `bookings.slot_id` is the final database guard.
- Retry-safe booking. Clients can attach an `Idempotency-Key`; repeated requests with the same payload replay the original booking, while key reuse with a different payload is rejected.
- Transactional history. Booking and cancellation events are written in the same database transaction as the state change and remain available after cancellation.
- No overlapping active slots for one doctor. Slot creation locks the doctor row, then checks interval overlap inside the same transaction.
- Explicit time semantics. API timestamps require an offset and are normalised to UTC.
- Separate health signals. `/health` reports process liveness; `/ready` verifies that the database is reachable.

The scope is intentionally narrow. Authentication, recurring appointments, clinician calendars and patient notifications are outside this repository's scope.

## Concurrency path

```text
POST /bookings
      |
      v
validate patient
      |
      v
SELECT slot ... FOR UPDATE  <--- competing transactions wait here
      |
      v
check existing booking
      |
      v
INSERT booking + event
      |
      v
COMMIT                      <--- UNIQUE(slot_id/key) remain the backstops
```

The MySQL integration tests exercise both contention and transport retries. Fifty independent booking attempts produce one `201`, 49 `409` responses and one row; fifty requests sharing one idempotency key all replay the same booking.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/patients` | Register a patient |
| `POST` | `/doctors` | Register a doctor |
| `POST` | `/slots` | Create a non-overlapping appointment slot |
| `GET` | `/availability` | List future, active, unbooked slots |
| `POST` | `/bookings` | Book a slot transactionally; accepts `Idempotency-Key` |
| `DELETE` | `/bookings/{id}` | Cancel a booking |
| `GET` | `/health` | Process liveness |
| `GET` | `/ready` | Database readiness |

OpenAPI documentation is available at `http://localhost:8000/docs` while the service is running.

## Run it

Docker Desktop and Docker Compose are the only local prerequisites.

```bash
git clone https://github.com/arkkn0/clinical-scheduling-system.git
cd clinical-scheduling-system
docker compose up --build
```

Compose starts MySQL, runs the Alembic migration, and then starts the API. Verify it with:

```bash
curl http://localhost:8000/ready
# {"status":"ready"}
```

Development credentials in `docker-compose.yml` are local defaults. Override `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD` in any shared environment.

## Test it

Fast feedback uses SQLite and skips the database-specific row-lock test:

```bash
pip install -r requirements.txt
pytest
ruff check .
```

To exercise MySQL locking locally, start the database and point the tests at it:

```bash
docker compose up -d mysql
$env:TEST_DATABASE_URL="mysql+pymysql://clinical:clinical_dev@127.0.0.1:3306/clinical_scheduling"
pytest
```

On macOS or Linux, use `export TEST_DATABASE_URL=...`. GitHub Actions runs the full suite against a MySQL 8 service on every push and pull request.

## Design notes

### Why both a row lock and a unique constraint?

The lock makes the expected conflict path deterministic and lets the API return a useful `409`. The constraint protects the invariant if a later code path forgets to acquire that lock. Correctness should not depend on every future caller remembering the same application convention.

### Why lock the doctor when creating a slot?

An overlap is a range rule rather than a simple equality rule. MySQL has no exclusion constraint for time ranges, so concurrent range checks could both pass. Locking the doctor gives all slot writes for that doctor a shared row on which to serialise.

### Why Alembic instead of creating tables on startup?

Application startup is not a schema versioning strategy. The checked-in migration makes database changes reviewable and repeatable across local, CI and deployment environments.

### Why do booking events keep identifiers without foreign keys?

The event row is a snapshot of a state change, not another mutable view of the booking. A cancellation deletes the active booking so the slot becomes available again, but its `booked` and `cancelled` events remain. A cascading foreign key would erase the history the table exists to retain.

### What is the idempotency-key scope?

An idempotency key represents one booking intent and is retained for the life of that booking. Transport retries should reuse it; a new booking intent should always use a new key. Reusing a live key with another patient or slot returns `409`.

### AWS status

The container can run on a managed-container or VM platform with a managed MySQL database. This repository does not include deployed AWS infrastructure or claim infrastructure benchmarks.

## Structure

```text
app/
  main.py                 application and health endpoints
  database.py             engine and session lifecycle
  models.py               relational constraints
  schemas.py              request validation and UTC normalisation
  routers/                HTTP boundary
  services/bookings.py    booking transaction
alembic/                  versioned schema migration
tests/
  test_api.py             API behaviour and interval rules
  test_concurrency.py     MySQL contention and retry integration tests
.github/workflows/ci.yml  lint, migration and MySQL test job
```

## License

MIT
