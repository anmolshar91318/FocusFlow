"""
FocusFlow AI Assistant Module
Integrates Google Gemini API with user productivity data (tasks, focus sessions,
habits, level progression, achievements) to provide contextual, personalized study coaching.
Automatically queries model list and selects the lowest credit-consumption model (Flash models).
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from gamification import get_user_progression_summary

ENV_FILE = Path(__file__).resolve().parent / ".env"

# Preference order for lowest credit/cost consumption models
PREFERRED_LOW_CREDIT_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-flash-latest",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash",
    "gemini-2.0-flash",
]

# Robust fallback sequence used during chat to ensure 100% uptime
FALLBACK_CHAIN = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-flash-latest",
]

# Models reported as deprecated or unavailable to new users by Google
DEPRECATED_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
}

# Non-chat or specialized model keywords to filter out
DISALLOWED_KEYWORDS = [
    "tts",
    "image",
    "transcribe",
    "robotics",
    "computer-use",
    "banana",
    "lyria",
    "antigravity",
    "deep-research",
    "customtools",
]


def classify_credit_tier(model_id: str) -> str:
    """Classifies model by credit/token consumption tier."""
    lid = model_id.lower()
    if "flash-lite" in lid or "lite" in lid:
        return "Ultra Low Credit (Flash-Lite)"
    elif "flash" in lid:
        return "Low Credit (Flash)"
    elif "pro" in lid:
        return "Higher Credit (Pro)"
    elif "gemma" in lid:
        return "Open Weights (Gemma)"
    return "Standard"


def load_env_file():
    """Loads environment variables from backend/.env if present."""
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass


load_env_file()


def get_api_key(db: sqlite3.Connection = None, user_id: int = None) -> str:
    """
    Retrieves Gemini API key. Checks:
    1. User's stored key in database (if available)
    2. Environment variable GEMINI_API_KEY
    """
    if db and user_id:
        try:
            row = db.execute(
                "SELECT gemini_api_key FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if row and row["gemini_api_key"] and row["gemini_api_key"].strip():
                return row["gemini_api_key"].strip()
        except sqlite3.OperationalError:
            pass

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return key


def save_api_key(db: sqlite3.Connection, user_id: int, api_key: str):
    """Saves API key for the user and writes to .env for persistence."""
    api_key = str(api_key).strip()

    # Ensure column exists
    cols = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
    if "gemini_api_key" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN gemini_api_key TEXT DEFAULT ''")

    db.execute("UPDATE users SET gemini_api_key=? WHERE id=?", (api_key, user_id))
    db.commit()

    # Also update backend/.env
    os.environ["GEMINI_API_KEY"] = api_key
    try:
        lines = []
        if ENV_FILE.exists():
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                lines = [l for l in f.readlines() if not l.startswith("GEMINI_API_KEY=")]
        lines.append(f"GEMINI_API_KEY={api_key}\n")
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass


def fetch_gemini_models(api_key: str):
    """
    Calls Google Gemini's List Models API to discover available models.
    Filters out deprecated and non-chat models, categorizes by credit tier,
    and returns a prioritized list with the lowest credit-consumption model recommended.
    """
    if not api_key:
        return {
            "models": [],
            "recommended_model": "gemini-3.5-flash-lite",
            "error": "No Gemini API key provided",
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "FocusFlow/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_msg)
            message = err_json.get("error", {}).get("message", str(e))
        except Exception:
            message = str(e)
        return {
            "models": [],
            "recommended_model": "gemini-3.5-flash-lite",
            "error": message,
        }
    except Exception as e:
        return {
            "models": [],
            "recommended_model": "gemini-3.5-flash-lite",
            "error": str(e),
        }

    raw_models = data.get("models", [])
    valid_models = []

    for m in raw_models:
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue

        full_name = m.get("name", "")
        short_name = full_name.replace("models/", "").strip()
        display_name = m.get("displayName", short_name)
        desc = m.get("description", "")

        # Skip deprecated and non-chat / specialized models
        if short_name in DEPRECATED_MODELS:
            continue
        if any(k in short_name.lower() for k in DISALLOWED_KEYWORDS):
            continue

        tier = classify_credit_tier(short_name)

        valid_models.append(
            {
                "id": short_name,
                "name": full_name,
                "display_name": display_name,
                "description": desc,
                "credit_tier": tier,
            }
        )

    # Sort models by credit preference:
    # 1. Models in PREFERRED_LOW_CREDIT_MODELS in exact order
    # 2. Other Flash-Lite models
    # 3. Other Flash models
    # 4. Pro / Gemma models
    def sort_key(vm):
        mid = vm["id"]
        if mid in PREFERRED_LOW_CREDIT_MODELS:
            return (0, PREFERRED_LOW_CREDIT_MODELS.index(mid))
        if "flash-lite" in mid.lower() or "lite" in mid.lower():
            return (1, 0)
        if "flash" in mid.lower():
            return (2, 0)
        return (3, 0)

    valid_models.sort(key=sort_key)

    # Pick the recommended model: first preferred model in the list
    recommended = None
    if valid_models:
        recommended = valid_models[0]["id"]

    return {
        "models": valid_models,
        "recommended_model": recommended or "gemini-3.5-flash-lite",
        "error": None,
    }


def build_user_context(db: sqlite3.Connection, user_id: int) -> str:
    """
    Gathers comprehensive live user productivity data to ground the AI assistant.
    Includes tasks, focus history, progression, achievements, and habits.
    """
    user_row = db.execute("SELECT name, email FROM users WHERE id=?", (user_id,)).fetchone()
    user_name = user_row["name"] if user_row else "Student"

    # Tasks
    tasks = db.execute(
        "SELECT id, title, category, priority, due_date, estimated_minutes, completed FROM tasks WHERE user_id=? ORDER BY completed ASC, priority DESC",
        (user_id,),
    ).fetchall()

    pending_tasks = [t for t in tasks if not t["completed"]]
    completed_tasks = [t for t in tasks if t["completed"]]

    # Sessions
    sessions = db.execute(
        "SELECT duration_minutes, completed_at FROM sessions WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (user_id,),
    ).fetchall()
    total_focus_mins = sum(s["duration_minutes"] for s in sessions)

    # Progression summary
    prog = get_user_progression_summary(db, user_id)

    # Today's date
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    context_lines = [
        f"You are the FocusFlow AI Assistant, a personal productivity coach and study mentor.",
        f"You are speaking with {user_name}.",
        f"Today's date is {today_str}.",
        "",
        "=== USER PRODUCTIVITY PROFILE ===",
        f"- Current Level: Level {prog['current_level']} ({prog['level_title']})",
        f"- Rank Tier: {prog['rank_tier']} ({prog['total_xp']} Total XP)",
        f"- Productivity Streak: {prog['current_streak']} consecutive days",
        f"- Weekly XP: {prog['weekly_xp']} XP earned this week",
        f"- Focus Stats: {prog['total_focus_hours']} hours completed across {prog['total_sessions']} focus blocks",
        f"- Achievements: {prog['unlocked_achievements_count']} of {prog['total_achievements_count']} badges unlocked",
    ]

    if prog.get("next_achievement"):
        na = prog["next_achievement"]
        context_lines.append(
            f"- Next Upcoming Badge: {na['name']} ({na['current_progress']}/{na['target']}) - {na['description']}"
        )

    context_lines.append("\n=== ACTIVE PENDING TASKS ===")
    if not pending_tasks:
        context_lines.append("No pending tasks. The task list is completely clear!")
    else:
        for t in pending_tasks[:12]:
            due = f" (Due: {t['due_date']})" if t["due_date"] else ""
            context_lines.append(
                f"- [ID:{t['id']}] \"{t['title']}\" | Priority: {t['priority']} | Category: {t['category']} | Est: {t['estimated_minutes']}m{due}"
            )

    context_lines.append(f"\n=== COMPLETED TASKS ({len(completed_tasks)} completed) ===")
    for t in completed_tasks[:5]:
        context_lines.append(f"- \"{t['title']}\" ({t['category']})")

    context_lines.extend(
        [
            "",
            "=== ASSISTANT INSTRUCTIONS (STRICT BREVITY & EFFICIENCY) ===",
            "1. CONCISENESS FIRST (CRITICAL): Keep every response as short and low-text as possible. Aim for 1-3 concise sentences or brief bullet points. Avoid filler phrases, preambles, and walls of text.",
            "2. GREETINGS & CASUAL CHAT: When the user says 'hello', 'hi', 'hey', 'thanks', or casual greetings, reply warmly in just 1-2 short sentences (e.g. 'Hello Anmol! Ready to focus? What are we tackling today?'). Do NOT dump unprompted guides, task lists, or study schedules on simple greetings.",
            "3. DIRECT & ACTIONABLE: Cut straight to the point. No conversational fluff ('Certainly!', 'I would be happy to help').",
            "4. GROUNDING: Refer directly to their single highest-priority task or current focus streak when advice is requested.",
            "5. TASK REFERENCING: When referring to an existing task, include [TASK_REF: id] so the user can click to start a timer or complete it.",
            "6. SUGGESTING NEW TASKS: Only when recommending a concrete new task, format it strictly on its own line like:",
            '   [NEW_TASK: {"title": "Task title", "priority": "High|Medium|Low", "category": "Study|Assignment|Exam preparation|Personal|Project", "estimated_minutes": 25, "due_date": ""}]',
            "7. MINIMAL TOKEN USAGE: Respect user credits by keeping total output tokens as low as possible while delivering clear value.",
        ]
    )

    return "\n".join(context_lines)


def generate_chat_response(
    db: sqlite3.Connection,
    user_id: int,
    messages: list,
    model_name: str = None,
):
    """
    Sends message history to Gemini API with grounded user context and returns response.
    Features intelligent multi-model fallback so requests never fail due to model deprecation,
    temporary 503 high demand spikes, or read timeouts.
    """
    api_key = get_api_key(db, user_id)
    if not api_key:
        return {
            "reply": (
                "Welcome to your FocusFlow AI Assistant! To get started, please connect your **Google Gemini API Key**.\n\n"
                "You can get a free key in under 1 minute from [Google AI Studio](https://aistudio.google.com/app/apikey). "
                "Click the **Configure Gemini API Key** button above to paste it."
            ),
            "cards": [],
            "model_used": None,
            "needs_key": True,
        }

    # Build system instructions
    system_instruction = build_user_context(db, user_id)

    # Format contents for Gemini API (alternating user / model roles)
    gemini_contents = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        text = str(msg.get("content", "")).strip()
        if text:
            gemini_contents.append({"role": role, "parts": [{"text": text}]})

    if not gemini_contents:
        gemini_contents.append({"role": "user", "parts": [{"text": "Hello! What should I focus on right now?"}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": gemini_contents,
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": 350,
        },
    }

    # Build prioritized candidate models list for intelligent fallback
    candidate_models = []
    clean_requested = (model_name or "").replace("models/", "").strip()
    if clean_requested and clean_requested not in DEPRECATED_MODELS:
        candidate_models.append(clean_requested)

    for fallback_model in FALLBACK_CHAIN:
        if fallback_model not in candidate_models and fallback_model not in DEPRECATED_MODELS:
            candidate_models.append(fallback_model)

    data = None
    successful_model = None
    last_error = ""

    for candidate in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "FocusFlow/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                successful_model = candidate
                break
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_msg)
                msg = err_json.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)
            last_error = msg

            # If the API key is completely invalid across the account, no model fallback can succeed
            if "api_key" in msg.lower() or "api key not valid" in msg.lower():
                break

            # If model is deprecated (404), overloaded (503), rate limited on model (429), or server error (500):
            # Continue to the next fallback model in the chain
            continue
        except Exception as e:
            last_error = str(e)
            continue

    if not data or not successful_model:
        return {
            "reply": f"⚠️ **Gemini API Error**: {last_error or 'All candidate models were temporarily unavailable.'}\n\nPlease check your API key in settings or try again in a few moments.",
            "cards": [],
            "model_used": None,
            "error": last_error,
        }

    # Extract text from response
    candidates = data.get("candidates", [])
    if not candidates:
        return {
            "reply": "No response was generated by the model. Please try a different question.",
            "cards": [],
            "model_used": successful_model,
        }

    reply_text = ""
    parts = candidates[0].get("content", {}).get("parts", [])
    for p in parts:
        if "text" in p:
            reply_text += p["text"]

    # Parse actionable task cards
    cards = []

    # 1. Parse [NEW_TASK: {...}] tags
    new_task_pattern = re.compile(r"\[NEW_TASK:\s*(\{.*?\})\s*\]", re.DOTALL)
    for match in new_task_pattern.finditer(reply_text):
        try:
            task_data = json.loads(match.group(1))
            cards.append(
                {
                    "type": "new_task_suggestion",
                    "title": task_data.get("title", "New Task"),
                    "category": task_data.get("category", "Study"),
                    "priority": task_data.get("priority", "Medium"),
                    "estimated_minutes": int(task_data.get("estimated_minutes", 25)),
                    "due_date": task_data.get("due_date", ""),
                }
            )
        except Exception:
            pass

    # Clean out [NEW_TASK: ...] tags from reply text
    cleaned_reply = new_task_pattern.sub("", reply_text)

    # 2. Parse [TASK_REF: id] tags
    task_ref_pattern = re.compile(r"\[TASK_REF:\s*(\d+)\s*\]")
    for match in task_ref_pattern.finditer(cleaned_reply):
        try:
            tid = int(match.group(1))
            t_row = db.execute(
                "SELECT id, title, category, priority, due_date, estimated_minutes, completed FROM tasks WHERE id=? AND user_id=?",
                (tid, user_id),
            ).fetchone()
            if t_row:
                cards.append(
                    {
                        "type": "existing_task",
                        "id": t_row["id"],
                        "title": t_row["title"],
                        "category": t_row["category"],
                        "priority": t_row["priority"],
                        "estimated_minutes": t_row["estimated_minutes"],
                        "due_date": t_row["due_date"],
                        "completed": bool(t_row["completed"]),
                    }
                )
        except Exception:
            pass

    # Clean out [TASK_REF: ...] tags from reply text
    cleaned_reply = task_ref_pattern.sub("", cleaned_reply).strip()

    # If cards were found, ensure uniqueness by title
    seen_titles = set()
    unique_cards = []
    for c in cards:
        if c.get("title") not in seen_titles:
            seen_titles.add(c.get("title"))
            unique_cards.append(c)

    return {
        "reply": cleaned_reply,
        "cards": unique_cards,
        "model_used": successful_model,
        "needs_key": False,
    }
