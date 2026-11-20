import os
import re
import secrets
from datetime import datetime, timezone, timedelta
import sqlite3
from pathlib import Path
from functools import wraps
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from database import connect, init_database, USE_POSTGRES, NEON_DATABASE_URL
from email_service import send_verification_email, send_password_reset_email
from gamification import (
    calculate_session_xp,
    award_xp,
    update_user_streak_and_award_bonus,
    check_weekly_focus_goal_bonus,
    check_and_unlock_achievements,
    get_user_progression_summary,
    get_or_init_progression,
    XP_PER_TASK,
)
from ai_assistant import (
    get_api_key,
    save_api_key,
    fetch_gemini_models,
    generate_chat_response,
)

app = Flask(__name__)

# Session Cookie Configuration:
# In cross-origin environments (e.g. frontend on vercel or localhost talking to backend on vercel),
# browsers require SameSite=None and Secure=True to transmit session cookies with credentials: 'include'.
is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
cookie_samesite = os.environ.get("SESSION_COOKIE_SAMESITE", "None" if is_vercel else "Lax")
cookie_secure = (
    os.environ.get("SESSION_COOKIE_SECURE", "true" if is_vercel else "false").lower() in ("true", "1")
)

app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "focusflow-production-secret-key-replace-if-needed"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=cookie_samesite,
    SESSION_COOKIE_SECURE=cookie_secure,
)

# Setup CORS with Flask-CORS
# By allowing pattern r".*", Flask-CORS echoes the exact requesting Origin back
# with Access-Control-Allow-Credentials: true, complying with W3C Fetch spec.
CORS(
    app,
    supports_credentials=True,
    resources={r"/*": {"origins": r".*"}},
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "Cookie"],
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    expose_headers=["Content-Type", "Set-Cookie"],
)


@app.before_request
def handle_options_preflight():
    """Immediately return 200 OK with full CORS headers on preflight OPTIONS requests."""
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin") or "*"
        res = app.make_default_options_response()
        res.headers["Access-Control-Allow-Origin"] = origin
        res.headers["Access-Control-Allow-Credentials"] = "true"
        res.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        res.headers["Access-Control-Allow-Headers"] = (
            request.headers.get("Access-Control-Request-Headers")
            or "Content-Type, Authorization, X-Requested-With, Accept, Cookie"
        )
        res.headers["Access-Control-Max-Age"] = "86400"
        return res


@app.after_request
def ensure_cors_headers(response):
    """Guarantees CORS headers are attached on all responses, including errors and custom codes."""
    origin = request.headers.get("Origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Requested-With, Accept, Cookie"
        )
    return response


def init_db():
    init_database()
    try:
        with connect() as db:
            existing_users = db.execute("SELECT id FROM users").fetchall()
            for u in existing_users:
                get_or_init_progression(db, u["id"])
                check_and_unlock_achievements(db, u["id"])
            db.commit()
    except Exception as e:
        print(f"[FocusFlow DB] Notice during progression init: {e}")


# Call init_db on module import so tables exist even when running under serverless / WSGI
try:
    init_db()
except Exception as e:
    print(f"[FocusFlow DB] Startup initialization notice: {e}")


@app.get("/")
def index():
    return jsonify({
        "name": "FocusFlow API",
        "status": "online",
        "database": "Neon PostgreSQL" if USE_POSTGRES else "SQLite",
        "endpoints": {
            "health": "/api/health",
            "auth": "/api/auth/me",
            "tasks": "/api/tasks",
            "sessions": "/api/sessions",
            "progression": "/api/progression",
            "achievements": "/api/achievements",
            "ai": "/api/ai/chat"
        }
    })


def generate_otp(length=6) -> str:
    """Generates a cryptographically secure numeric OTP."""
    return "".join(secrets.choice("0123456789") for _ in range(length))


def is_code_valid(stored_code: str, stored_expiry: str, input_code: str) -> tuple[bool, str]:
    """Validates an OTP against stored code and ISO timestamp expiration."""
    if not stored_code or not stored_expiry:
        return False, "No active code found. Please request a new code."
    if str(stored_code).strip() != str(input_code).strip():
        return False, "Invalid code. Please check and try again."
    try:
        expiry_str = str(stored_expiry).strip()
        expiry_dt = datetime.fromisoformat(expiry_str)
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expiry_dt:
            return False, "The code has expired. Please request a new code."
    except Exception:
        return False, "Code verification failed or format is invalid."
    return True, ""


def user_payload(row):
    is_verified = bool(row["is_verified"]) if "is_verified" in row.keys() else True
    return {"id": row["id"], "name": row["name"], "email": row["email"], "is_verified": is_verified}


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
    data["xp_awarded"] = bool(data.get("xp_awarded", 0))
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
        row = db.execute("SELECT id,name,email,is_verified FROM users WHERE id=?", (uid,)).fetchone()
    if row is None:
        session.clear()
        return jsonify({"user": None})
    return jsonify({"user": user_payload(row)})


@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not 2 <= len(name) <= 60:
        return jsonify({"error": "Name must be between 2 and 60 characters."}), 400
    if "@" not in email or len(email) > 120:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must contain at least 8 characters."}), 400

    code = generate_otp(6)
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        with connect() as db:
            existing = db.execute("SELECT id, name, is_verified FROM users WHERE LOWER(email)=?", (email,)).fetchone()
            if existing:
                if bool(existing["is_verified"]):
                    return jsonify({"error": "An account with this email already exists. Please log in."}), 409
                # Unverified account already exists: refresh credentials & verification code
                db.execute(
                    """UPDATE users 
                       SET name=?, password_hash=?, verification_code=?, verification_code_expires_at=? 
                       WHERE id=?""",
                    (name, generate_password_hash(password), code, expiry, existing["id"]),
                )
                uid = existing["id"]
            else:
                cur = db.execute(
                    """INSERT INTO users(name, email, password_hash, created_at, is_verified, verification_code, verification_code_expires_at)
                       VALUES(?,?,?,?,0,?,?)""",
                    (name, email, generate_password_hash(password), now_iso, code, expiry),
                )
                uid = cur.lastrowid
                if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
                    db.execute("UPDATE tasks SET user_id=? WHERE user_id IS NULL", (uid,))
                    db.execute("UPDATE sessions SET user_id=? WHERE user_id IS NULL", (uid,))
                # Initialize user progression
                get_or_init_progression(db, uid)

            db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists. Please log in."}), 409

    # Send verification email via Google SMTP
    email_res = send_verification_email(email, name, code)

    return jsonify({
        "status": "verification_required",
        "email": email,
        "message": f"Verification code sent to {email}. Please enter the 6-digit code to activate your account.",
        "email_sent": email_res.get("success", False),
    }), 201


@app.post("/api/auth/verify-email")
def verify_email():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    code = str(data.get("code", "")).strip()

    if not email or not code:
        return jsonify({"error": "Email and 6-digit verification code are required."}), 400

    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (email,)).fetchone()
        if row is None:
            return jsonify({"error": "No account found with this email."}), 404

        if bool(row["is_verified"]):
            session.clear()
            session["user_id"] = row["id"]
            return jsonify({"message": "Email is already verified.", "user": user_payload(row)}), 200

        valid, err_msg = is_code_valid(row["verification_code"], row["verification_code_expires_at"], code)
        if not valid:
            return jsonify({"error": err_msg}), 400

        db.execute(
            "UPDATE users SET is_verified=1, verification_code='', verification_code_expires_at='' WHERE id=?",
            (row["id"],),
        )
        db.commit()
        updated_row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
        get_or_init_progression(db, row["id"])
        check_and_unlock_achievements(db, row["id"])

    session.clear()
    session["user_id"] = row["id"]
    return jsonify({
        "message": "Email verified successfully! Welcome to FocusFlow.",
        "user": user_payload(updated_row),
    }), 200


@app.post("/api/auth/resend-verification")
def resend_verification():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email address."}), 400

    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (email,)).fetchone()
        if row is None:
            return jsonify({"message": "If an unverified account with this email exists, a code was sent."}), 200

        if bool(row["is_verified"]):
            return jsonify({"message": "This email is already verified. You can log in directly."}), 200

        code = generate_otp(6)
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        db.execute(
            "UPDATE users SET verification_code=?, verification_code_expires_at=? WHERE id=?",
            (code, expiry, row["id"]),
        )
        db.commit()
        send_verification_email(row["email"], row["name"], code)

    return jsonify({"message": f"A new 6-digit verification code has been sent to {email}."}), 200


@app.post("/api/auth/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "Enter a valid email address."}), 400

    with connect() as db:
        row = db.execute("SELECT id, name, email FROM users WHERE LOWER(email)=?", (email,)).fetchone()
        if row is not None:
            code = generate_otp(6)
            expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            db.execute(
                "UPDATE users SET reset_code=?, reset_code_expires_at=? WHERE id=?",
                (code, expiry, row["id"]),
            )
            db.commit()
            send_password_reset_email(row["email"], row["name"], code)

    return jsonify({
        "message": "If an account exists with this email, a 6-digit password reset code has been sent."
    }), 200


@app.post("/api/auth/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    code = str(data.get("code", "")).strip()
    new_password = str(data.get("new_password", ""))

    if not email or not code:
        return jsonify({"error": "Email and 6-digit reset code are required."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "New password must contain at least 8 characters."}), 400

    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (email,)).fetchone()
        if row is None:
            return jsonify({"error": "Invalid email or reset code."}), 400

        valid, err_msg = is_code_valid(row["reset_code"], row["reset_code_expires_at"], code)
        if not valid:
            return jsonify({"error": err_msg}), 400

        new_hash = generate_password_hash(new_password)
        db.execute(
            "UPDATE users SET password_hash=?, reset_code='', reset_code_expires_at='', is_verified=1 WHERE id=?",
            (new_hash, row["id"]),
        )
        db.commit()

    return jsonify({"message": "Password reset successfully! You can now log in with your new password."}), 200


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE LOWER(email)=?", (email,)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            return jsonify({"error": "Incorrect email or password."}), 401

        is_verified = bool(row["is_verified"]) if "is_verified" in row.keys() else True
        if not is_verified:
            # Resend fresh verification code
            code = generate_otp(6)
            expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            db.execute(
                "UPDATE users SET verification_code=?, verification_code_expires_at=? WHERE id=?",
                (code, expiry, row["id"]),
            )
            db.commit()
            send_verification_email(row["email"], row["name"], code)
            return jsonify({
                "error": "Your email address is not verified yet. We have sent a 6-digit verification code to your email.",
                "needs_verification": True,
                "email": row["email"],
            }), 403

        # Ensure progression row and sync
        get_or_init_progression(db, row["id"])
        check_and_unlock_achievements(db, row["id"])

    session.clear()
    session["user_id"] = row["id"]
    return jsonify({"user": user_payload(row)})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@app.get("/api/tasks")
@login_required
def list_tasks():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM tasks WHERE user_id=? ORDER BY completed ASC, id DESC",
            (session["user_id"],),
        ).fetchall()
    return jsonify({"tasks": [task_dict(r) for r in rows]})


@app.post("/api/tasks")
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify({"error": "Task title is required."}), 400
    if len(title) > 120:
        return jsonify({"error": "Task title must be 120 characters or fewer."}), 400

    category = str(data.get("category", "Study"))
    priority = str(data.get("priority", "Medium"))
    if category not in {"Study", "Assignment", "Exam preparation", "Personal", "Project"}:
        category = "Study"
    if priority not in {"High", "Medium", "Low"}:
        priority = "Medium"

    due_date = str(data.get("due_date", ""))[:10]
    try:
        minutes = max(1, min(1440, int(data.get("estimated_minutes", 30))))
    except (ValueError, TypeError):
        minutes = 30

    created = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        cur = db.execute(
            """INSERT INTO tasks(title,category,priority,due_date,estimated_minutes,completed,created_at,user_id,xp_awarded)
               VALUES(?,?,?,?,?,0,?,?,0)""",
            (title, category, priority, due_date, minutes, created, session["user_id"]),
        )
        row = db.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"task": task_dict(row)}), 201


@app.patch("/api/tasks/<int:task_id>")
@login_required
def change_task(task_id):
    data = request.get_json(silent=True) or {}
    user_id = session["user_id"]

    with connect() as db:
        row = db.execute(
            "SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Task not found."}), 404

        was_completed = bool(row["completed"])
        was_xp_awarded = bool(row["xp_awarded"])
        completed_target = (
            bool(data["completed"])
            if isinstance(data.get("completed"), bool)
            else was_completed
        )
        title = (
            str(data["title"]).strip()[:120]
            if isinstance(data.get("title"), str) and data["title"].strip()
            else row["title"]
        )

        xp_earned = 0
        leveled_up = False
        new_level = None
        new_title = None
        streak_bonus = 0
        newly_unlocked = []

        # If marking complete and XP not yet awarded for this task
        if completed_target and not was_completed and not was_xp_awarded:
            db.execute(
                "UPDATE tasks SET completed=1, title=?, xp_awarded=1 WHERE id=? AND user_id=?",
                (title, task_id, user_id),
            )
            # Award task XP
            xp_res = award_xp(
                db,
                user_id,
                XP_PER_TASK,
                "task",
                f"task:{task_id}",
                f"Completed task: {title[:40]}",
            )
            if xp_res["awarded"]:
                xp_earned = XP_PER_TASK
                leveled_up = xp_res.get("leveled_up", False)
                new_level = xp_res.get("new_level")
                new_title = xp_res.get("new_title")

            streak_res = update_user_streak_and_award_bonus(db, user_id)
            streak_bonus = streak_res.get("bonus_xp", 0)
            newly_unlocked = check_and_unlock_achievements(db, user_id)
        else:
            # Update title or completion without duplicate XP
            db.execute(
                "UPDATE tasks SET completed=?, title=? WHERE id=? AND user_id=?",
                (1 if completed_target else 0, title, task_id, user_id),
            )

        updated = db.execute(
            "SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user_id)
        ).fetchone()
        progression = get_user_progression_summary(db, user_id)

    return jsonify(
        {
            "task": task_dict(updated),
            "xp_earned": xp_earned,
            "leveled_up": leveled_up,
            "new_level": new_level,
            "new_title": new_title,
            "streak_bonus": streak_bonus,
            "newly_unlocked_achievements": newly_unlocked,
            "progression": progression,
        }
    )


@app.delete("/api/tasks/<int:task_id>")
@login_required
def remove_task(task_id):
    with connect() as db:
        cur = db.execute(
            "DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, session["user_id"])
        )
    if cur.rowcount == 0:
        return jsonify({"error": "Task not found."}), 404
    return jsonify({"message": "Task deleted."})


@app.get("/api/sessions")
@login_required
def list_sessions():
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM sessions WHERE user_id=? ORDER BY id DESC LIMIT 50",
            (session["user_id"],),
        ).fetchall()
    return jsonify({"sessions": [dict(r) for r in rows]})


@app.post("/api/sessions")
@login_required
def add_session():
    data = request.get_json(silent=True) or {}
    user_id = session["user_id"]

    try:
        minutes = int(data.get("duration_minutes", 25))
    except (TypeError, ValueError):
        minutes = 25

    if not 1 <= minutes <= 180:
        return jsonify({"error": "Session duration must be between 1 and 180 minutes."}), 400

    stamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    xp_amount = calculate_session_xp(minutes)

    with connect() as db:
        cur = db.execute(
            "INSERT INTO sessions(duration_minutes,completed_at,user_id,xp_awarded) VALUES(?,?,?,1)",
            (minutes, stamp, user_id),
        )
        session_id = cur.lastrowid
        row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()

        # Award session XP
        xp_res = award_xp(
            db,
            user_id,
            xp_amount,
            "session",
            f"session:{session_id}",
            f"{minutes}-minute focus block",
        )

        streak_res = update_user_streak_and_award_bonus(db, user_id)
        weekly_res = check_weekly_focus_goal_bonus(db, user_id)
        newly_unlocked = check_and_unlock_achievements(db, user_id)
        progression = get_user_progression_summary(db, user_id)

    return (
        jsonify(
            {
                "session": dict(row),
                "xp_earned": xp_amount,
                "leveled_up": xp_res.get("leveled_up", False),
                "new_level": xp_res.get("new_level"),
                "new_title": xp_res.get("new_title"),
                "streak_bonus": streak_res.get("bonus_xp", 0),
                "weekly_bonus": weekly_res.get("xp", 0),
                "newly_unlocked_achievements": newly_unlocked,
                "progression": progression,
            }
        ),
        201,
    )


@app.get("/api/progression")
@login_required
def user_progression():
    with connect() as db:
        summary = get_user_progression_summary(db, session["user_id"])
    return jsonify({"progression": summary})


@app.get("/api/achievements")
@login_required
def user_achievements():
    with connect() as db:
        summary = get_user_progression_summary(db, session["user_id"])
    return jsonify({"achievements": summary["achievements"]})


@app.get("/api/ai/config")
@login_required
def get_ai_config():
    with connect() as db:
        key = get_api_key(db, session["user_id"])
        models_data = (
            fetch_gemini_models(key)
            if key
            else {"models": [], "recommended_model": "gemini-1.5-flash", "error": None}
        )

    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) >= 12 else ("Set" if key else "")
    return jsonify(
        {
            "has_key": bool(key),
            "masked_key": masked_key,
            "models": models_data.get("models", []),
            "recommended_model": models_data.get("recommended_model") or "gemini-1.5-flash",
            "error": models_data.get("error"),
        }
    )


@app.post("/api/ai/config")
@login_required
def set_ai_config():
    data = request.get_json(silent=True) or {}
    key = str(data.get("api_key", "")).strip()
    if not key:
        return jsonify({"error": "Gemini API key is required."}), 400

    models_data = fetch_gemini_models(key)
    if models_data.get("error"):
        return jsonify({"error": f"Invalid Gemini API key: {models_data['error']}"}), 400

    with connect() as db:
        save_api_key(db, session["user_id"], key)

    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) >= 12 else "Set"
    return jsonify(
        {
            "status": "ok",
            "has_key": True,
            "masked_key": masked_key,
            "models": models_data.get("models", []),
            "recommended_model": models_data.get("recommended_model") or "gemini-1.5-flash",
            "message": "Gemini API key verified and saved successfully.",
        }
    )


@app.post("/api/ai/chat")
@login_required
def ai_chat():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    model_name = data.get("model")

    if not isinstance(messages, list) or not messages:
        return jsonify({"error": "Messages array is required."}), 400

    with connect() as db:
        result = generate_chat_response(db, session["user_id"], messages, model_name)

    return jsonify(result)


if __name__ == "__main__":
    init_db()
    print("FocusFlow API: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
