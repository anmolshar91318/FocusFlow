# FocusFlow — Smart Productivity Management System

A React + Flask + Neon PostgreSQL web application with account registration/login, per-user tasks and focus history, a Pomodoro timer, rule-based task suggestions, and a remembered day/night theme switch.

## Requirements
- Python 3.10 or newer
- Node.js LTS (includes npm)
- VS Code

## First-time setup

### 1. Backend
Open a terminal in the project folder and run:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, run this once in that terminal and retry activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Keep the backend terminal open. Flask runs at `http://localhost:5000`.

### 2. Frontend
Open a second terminal in VS Code (click the `+` beside the terminal tab):

```powershell
cd frontend
npm install
npm run dev
```

Keep this terminal open too. Open the Vite address shown in the terminal, normally `http://localhost:5173`.
