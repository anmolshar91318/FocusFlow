from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from functools import wraps
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(SECRET_KEY="focusflow-local-development-key-change-before-deployment", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})
DB = Path(__file__).with_name("focusflow.db")

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Study', priority TEXT NOT NULL DEFAULT 'Medium', due_date TEXT NOT NULL DEFAULT '', estimated_minutes INTEGER NOT NULL DEFAULT 30, completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, user_id INTEGER REFERENCES users(id))""")
        db.execute("""CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, duration_minutes INTEGER NOT NULL, completed_at TEXT NOT NULL, user_id INTEGER REFERENCES users(id))""")
        for table in ("tasks", "sessions"):
            cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in cols:
                db.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")

def user_payload(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"]}

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in to continue."}), 401
        return fn(*args, **kwargs)
    return wrapped

def task_dict(row):
    data = dict(row)
    data["completed"] = bool(data["completed"])
    return data

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "message": "FocusFlow API is running"})

@app.get("/api/auth/me")
def current_user():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"user": None})
    with connect() as db:
        row = db.execute("SELECT id,name,email FROM users WHERE id=?", (uid,)).fetchone()
    if row is None:
        session.clear()
        return jsonify({"user": None})
    return jsonify({"user": user_payload(row)})

@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name, email, password = str(data.get("name", "")).strip(), str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
    if not 2 <= len(name) <= 60:
        return jsonify({"error": "Name must be between 2 and 60 characters."}), 400
    if "@" not in email or len(email) > 120:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must contain at least 8 characters."}), 400
    try:
        with connect() as db:
            cur = db.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)", (name, email, generate_password_hash(password), datetime.now(timezone.utc).isoformat()))
            uid = cur.lastrowid
            if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
                db.execute("UPDATE tasks SET user_id=? WHERE user_id IS NULL", (uid,))
                db.execute("UPDATE sessions SET user_id=? WHERE user_id IS NULL", (uid,))
            row = db.execute("SELECT id,name,email FROM users WHERE id=?", (uid,)).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists. Please log in."}), 409
    session.clear(); session["user_id"] = uid
    return jsonify({"user": user_payload(row)}), 201

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email, password = str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Incorrect email or password."}), 401
    session.clear(); session["user_id"] = row["id"]
    return jsonify({"user": user_payload(row)})

@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})

@app.get("/api/tasks")
@login_required
def list_tasks():
    with connect() as db:
        rows = db.execute("SELECT * FROM tasks WHERE user_id=? ORDER BY completed ASC, id DESC", (session["user_id"],)).fetchall()
    return jsonify({"tasks": [task_dict(r) for r in rows]})

@app.post("/api/tasks")
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title: return jsonify({"error": "Task title is required."}), 400
    if len(title) > 120: return jsonify({"error": "Task title must be 120 characters or fewer."}), 400
    category = str(data.get("category", "Study")); priority = str(data.get("priority", "Medium"))
    if category not in {"Study", "Assignment", "Exam preparation", "Personal", "Project"}: category = "Study"
    if priority not in {"High", "Medium", "Low"}: priority = "Medium"
    due_date = str(data.get("due_date", ""))[:10]
    try: minutes = max(1, min(1440, int(data.get("estimated_minutes", 30))))
    except (ValueError, TypeError): minutes = 30
    created = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        cur = db.execute("INSERT INTO tasks(title,category,priority,due_date,estimated_minutes,completed,created_at,user_id) VALUES(?,?,?,?,?,0,?,?)", (title,category,priority,due_date,minutes,created,session["user_id"]))
        row = db.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"task": task_dict(row)}), 201

@app.patch("/api/tasks/<int:task_id>")
@login_required
def change_task(task_id):
    data = request.get_json(silent=True) or {}
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, session["user_id"])).fetchone()
        if row is None:
            return jsonify({"error": "Task not found."}), 404
        completed = int(data["completed"]) if isinstance(data.get("completed"), bool) else row["completed"]
        title = str(data["title"]).strip()[:120] if isinstance(data.get("title"), str) and data["title"].strip() else row["title"]
        db.execute("UPDATE tasks SET completed=?, title=? WHERE id=? AND user_id=?", (completed, title, task_id, session["user_id"]))
        updated = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, session["user_id"])).fetchone()
    return jsonify({"task": task_dict(updated)})

@app.delete("/api/tasks/<int:task_id>")
@login_required
def remove_task(task_id):
    with connect() as db: cur = db.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id,session["user_id"]))
    if cur.rowcount == 0: return jsonify({"error": "Task not found."}), 404
    return jsonify({"message": "Task deleted."})

@app.get("/api/sessions")
@login_required
def list_sessions():
    with connect() as db: rows = db.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY id DESC LIMIT 50", (session["user_id"],)).fetchall()
    return jsonify({"sessions": [dict(r) for r in rows]})

@app.post("/api/sessions")
@login_required
def add_session():
    data = request.get_json(silent=True) or {}
    try: minutes = int(data.get("duration_minutes", 25))
    except (TypeError, ValueError): minutes = 25
    if not 1 <= minutes <= 180: return jsonify({"error": "Session duration must be between 1 and 180 minutes."}), 400
    stamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    with connect() as db:
        cur = db.execute("INSERT INTO sessions(duration_minutes,completed_at,user_id) VALUES(?,?,?)", (minutes,stamp,session["user_id"]))
        row = db.execute("SELECT * FROM sessions WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"session": dict(row)}), 201

if __name__ == "__main__":
    init_db()
    print("FocusFlow API: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
