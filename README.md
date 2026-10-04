# MeetFlow

**Turn meeting conversations into actionable work.**

MeetFlow is an AI-powered meeting assistant that takes a meeting recording, understands what was discussed, and turns it into structured tasks, decisions, and follow-ups — ready for review and approval.

Instead of leaving important action items buried in long transcripts, MeetFlow helps teams move from *what was discussed* to *what needs to be done*.

> **Recordings in. Workflows out.**

---

## The Problem

Meetings generate valuable information, but important decisions and responsibilities are often lost in lengthy recordings or scattered notes.

Someone still has to listen to the recording, identify action items, figure out who is responsible, and manually organize the follow-ups.

MeetFlow reduces this manual effort by using AI to process meeting conversations and prepare actionable workflows.

## What MeetFlow Does

### 1. Upload Meeting Recordings
Upload a prerecorded meeting audio file and let MeetFlow process the conversation. The current version focuses on uploaded recordings, with live meeting integrations planned for the future.

### 2. Convert Speech into Transcripts
MeetFlow uses Google Gemini to transcribe meeting audio into readable, speaker-aware conversation segments, making discussions easier to review and search through.

### 3. Understand the Conversation
Using Google Gemma, MeetFlow analyzes the transcript to identify meaningful information, including:
- Key discussion points
- Decisions made during the meeting
- Tasks and action items
- Responsible participants
- Deadlines and follow-ups

### 4. Turn Decisions into Workflows
Extracted information is organized into structured action items instead of remaining buried in a transcript.

### 5. Review Before Execution
AI-generated actions are not executed automatically. Users can review, edit, approve, or reject proposed actions before execution.

### 6. Track Action Status
MeetFlow maintains action statuses and execution history, helping users understand what has been approved and what has been processed.

---

## How It Works

1. **Upload** — Add a prerecorded meeting audio file.
2. **Transcribe** — Gemini converts the audio into a transcript.
3. **Analyze** — Gemma identifies decisions, tasks, and follow-ups.
4. **Review** — Check and edit the proposed actions.
5. **Approve** — Explicitly authorize actions before execution.
6. **Track** — View action status and execution history.

---

## Built With

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, Tailwind CSS |
| Backend | Python, FastAPI, Uvicorn |
| Database | SQLite, SQLAlchemy |
| Audio Transcription | Google Gemini API |
| Workflow Extraction | Google Gemma |
| Testing | Pytest |
| Development | Git, GitHub |

---

## Architecture

MeetFlow separates the user interface, API, AI processing, and action execution into distinct layers.

```text
                ┌──────────────────────┐
                │     React Frontend   │
                │  Upload • Review     │
                │  Approve • Track     │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │     FastAPI Backend  │
                │  Meeting & Workflow  │
                │      Management      │
                └──────────┬───────────┘
                           │
                ┌──────────▼───────────┐
                │   AI Processing      │
                │                      │
                │ Gemini: Transcription│
                │ Gemma: Extraction    │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │   Approval Layer     │
                │  Review • Edit       │
                │  Approve • Reject    │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │  Execution Layer     │
                │  Status & History    │
                └──────────────────────┘
```

SQLite stores meeting and action data, while the backend manages processing, validation, approval, and execution states.

---

## Human Approval Comes First

MeetFlow follows a simple principle: **AI can propose actions, but the user decides what gets executed.**

Extracted tasks and workflows remain under user control. Actions must pass through the approval process before execution.

The current MVP uses a mock execution provider to demonstrate this lifecycle safely. It does not send real emails or create tasks in external applications.

---

## Current Status

MeetFlow currently supports:
- Prerecorded audio upload
- Gemini-powered audio transcription
- Gemma-powered workflow extraction
- Meeting and action management
- Editing, approving, and rejecting proposed actions
- Mock action execution and execution history

### Future Scope
- Live meeting integrations with platforms such as Zoom and Google Meet
- Real task-management integrations
- Email and calendar automation
- Additional workflow integrations

---

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js and npm
- Google AI Studio API key

### 1. Clone the Repository

```bash
git clone https://github.com/atharvshukla24/MeetFlow.git
cd MeetFlow
```

### 2. Configure the Backend

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env
```

Add your Google AI Studio API key to the root `.env` file and configure the required providers.

Never commit your `.env` file or expose your API key.

### 3. Start the Backend

From the project root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Backend API: `http://127.0.0.1:8000`

API documentation: `http://127.0.0.1:8000/docs`

### 4. Start the Frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL shown by Vite, usually `http://localhost:5173`.

---

## Running Tests

From the project root:

```bash
python -m pytest -v
```

---

## Project

**MeetFlow — From conversations to execution.**

Built with React, FastAPI, Gemini, and Gemma.

[GitHub Repository](https://github.com/atharvshukla24/MeetFlow)
