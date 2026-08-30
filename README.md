# Clinical Scheduling System

A small FastAPI and MySQL service built around one deceptively hard requirement: two patients must never own the same appointment slot, even when requests arrive together.

The project stays backend-only so the interesting parts remain visible: transaction boundaries, database constraints, interval conflicts, failure responses, migrations, and reproducible tests.

## What it guarantees

- One booking per slot. The booking transaction locks the slot row before it checks and writes; a unique constraint on `bookings.slot_id` is the final database guard.
- No overlapping active slots for one doctor. Slot creation locks the doctor row, then checks interval overlap inside the same transaction.
- Explicit time semantics. API timestamps require an offset and are normalised to UTC.
- Honest operational signals. `/health` reports process liveness; `/ready` verifies that the database is reachable.

These are deliberately narrow guarantees. Authentication, recurring appointments, clinician calendars and patient notifications are outside this repository's scope.

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
INSERT + COMMIT             <--- UNIQUE(slot_id) remains the backstop
```

The MySQL integration test sends 50 competing booking requests and asserts the invariant at both boundaries: exactly one `201`, 49 `409` responses, and one booking row.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/patients` | Register a patient |
| `POST` | `/doctors` | Register a doctor |
| `POST` | `/slots` | Create a non-overlapping appointment slot |
| `GET` | `/availability` | List future, active, unbooked slots |
| `POST` | `/bookings` | Book a slot transactionally |
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

### AWS status

The container can run on common managed-container or VM platforms and use a managed MySQL database, but this repository does not claim a live AWS deployment or benchmark infrastructure setup time. An earlier README blurred design intent with deployed evidence; this version keeps those distinct.

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
  test_concurrency.py     MySQL row-lock integration test
.github/workflows/ci.yml  lint, migration and MySQL test job
```

## License

MIT
