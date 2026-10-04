# MeetFlow

**MeetFlow** turns a prerecorded meeting into an approved, executable workflow.

This repository implements the MeetFlow application according to the specifications in [IMPLEMENTATION.md](file:///c:/_New%20Drive/meetflow/IMPLEMENTATION.md).

---

## Milestone 1: Backend Foundation

Milestone 1 establishes the production-ready FastAPI foundation, SQLite persistence layer with SQLAlchemy models, environment configuration, automated tests, and health checking endpoints.

### Repository Layout

```text
meetflow/
├── IMPLEMENTATION.md         # Full project implementation plan
├── README.md                 # Project documentation and Windows run instructions
├── .env.example              # Example environment configuration
├── .gitignore                # Safe Git exclusions
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI entrypoint with CORS, lifespan & health routes
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py     # Pydantic BaseSettings environment configuration
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   └── session.py    # SQLAlchemy SQLite engine, sessionmaker & get_db dependency
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # DeclarativeBase with timestamp mixin
│   │   │   ├── meeting.py    # Meeting SQLAlchemy model
│   │   │   └── action.py     # Action SQLAlchemy model (tasks, emails, reminders)
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── health.py     # Health response schemas
│   │   │   ├── meeting.py    # Meeting Pydantic validation schemas
│   │   │   └── action.py     # Action Pydantic validation schemas
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py     # Central API routing
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       └── health.py # Health check route handler with DB verification
│   │   └── services/
│   │       └── __init__.py   # Business logic package (for future milestones)
│   └── requirements.txt      # Python dependencies
└── tests/
    ├── __init__.py
    ├── conftest.py           # In-memory SQLite fixtures and TestClient setup
    └── test_health.py        # Automated tests for health endpoints and DB persistence
```

---

## Windows Setup and Run Instructions

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Windows PowerShell or Command Prompt

### Step 1: Clone or Navigate to Project Directory
```powershell
cd "c:\_New Drive\meetflow"
```

### Step 2: Create and Activate Virtual Environment
Using PowerShell:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell execution policy prevents running scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` or activate using Command Prompt: `venv\Scripts\activate.bat`)*

### Step 3: Install Dependencies
```powershell
pip install -r backend/requirements.txt
```

### Step 4: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

### Step 5: Run the Server
Launch the FastAPI development server:
```powershell
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

The server will be available at:
- **API Root**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) or [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Verifying the Health Endpoint

### In PowerShell:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get | ConvertTo-Json
```

Expected output:
```json
{
  "status": "healthy",
  "app": "MeetFlow API",
  "version": "0.1.0",
  "database": "connected",
  "environment": "development"
}
```

### With cURL:
```powershell
curl http://127.0.0.1:8000/health
```

---

## Running Automated Tests

Run the full pytest suite from the project root:
```powershell
python -m pytest -v
```

This verifies:
1. `GET /` root welcome endpoint
2. `GET /health` root health check and status contract
3. `GET /api/v1/health` v1 health check
4. SQLAlchemy SQLite model persistence and relationships (Meeting <-> Action)
