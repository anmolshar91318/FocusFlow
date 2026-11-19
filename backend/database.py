import os
import re
import shutil
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend/.env if present
load_dotenv(Path(__file__).with_name(".env"))

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

# Environment variable check for Neon / PostgreSQL
NEON_DATABASE_URL = (
    os.environ.get("NEON_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or ""
).strip()

# Adjust postgres:// to postgresql:// if needed for psycopg2
if NEON_DATABASE_URL.startswith("postgres://"):
    NEON_DATABASE_URL = "postgresql://" + NEON_DATABASE_URL[len("postgres://") :]

# Ensure sslmode=require for cloud Neon connections
if NEON_DATABASE_URL and "sslmode" not in NEON_DATABASE_URL:
    separator = "&" if "?" in NEON_DATABASE_URL else "?"
    NEON_DATABASE_URL = f"{NEON_DATABASE_URL}{separator}sslmode=require"

# Flag indicating whether Neon PostgreSQL is active
USE_POSTGRES = bool(NEON_DATABASE_URL and psycopg2 is not None)

# SQLite fallback path
BASE_DIR = Path(__file__).parent.resolve()
DEFAULT_SQLITE_PATH = BASE_DIR / "focusflow.db"


def _get_sqlite_path() -> Path:
    """Returns a writable SQLite file path, falling back to /tmp if read-only (e.g., on Vercel)."""
    # If running on Vercel or similar read-only serverless environment
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = Path("/tmp/focusflow.db")
        if not tmp_db.exists() and DEFAULT_SQLITE_PATH.exists():
            try:
                shutil.copy2(DEFAULT_SQLITE_PATH, tmp_db)
            except Exception:
                pass
        return tmp_db

    # Test writability of current directory / database file
    try:
        if DEFAULT_SQLITE_PATH.exists():
            with open(DEFAULT_SQLITE_PATH, "a"):
                pass
        else:
            with open(DEFAULT_SQLITE_PATH, "w"):
                pass
        return DEFAULT_SQLITE_PATH
    except (IOError, OSError, PermissionError):
        # Read-only filesystem fallback
        tmp_db = Path("/tmp/focusflow.db")
        if not tmp_db.exists() and DEFAULT_SQLITE_PATH.exists():
            try:
                shutil.copy2(DEFAULT_SQLITE_PATH, tmp_db)
            except Exception:
                pass
        return tmp_db


class DictLikeRow:
    """Provides sqlite3.Row-like access (by name and by index) for PostgreSQL query results."""

    def __init__(self, description, values):
        self._values = tuple(values)
        if description:
            self._map = {desc[0]: val for desc, val in zip(description, values)}
        else:
            self._map = {}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def get(self, key, default=None):
        return self._map.get(key, default)

    def keys(self):
        return self._map.keys()

    def values(self):
        return self._map.values()

    def items(self):
        return self._map.items()

    def __iter__(self):
        return iter(self._map.keys())

    def __contains__(self, key):
        return key in self._map

    def __repr__(self):
        return f"<Row {self._map}>"


def _translate_query(query: str) -> str:
    """Translates SQLite SQL query with '?' parameter markers to PostgreSQL '%s'."""
    parts = []
    tokens = re.split(r"('(?:''|[^'])*')", query)
    for i, token in enumerate(tokens):
        if i % 2 == 1:
            parts.append(token)
        else:
            parts.append(token.replace("?", "%s"))
    return "".join(parts)


class PostgresCursorWrapper:
    """Wraps psycopg2 cursor to mirror sqlite3 cursor methods and properties."""

    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DictLikeRow(self._cursor.description, row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        desc = self._cursor.description
        return [DictLikeRow(desc, r) for r in rows]

    def __iter__(self):
        for r in self._cursor:
            yield DictLikeRow(self._cursor.description, r)


class PostgresConnectionWrapper:
    """Context manager and connection wrapper for PostgreSQL."""

    def __init__(self, dsn):
        self._dsn = dsn
        self._conn = psycopg2.connect(dsn)

    def execute(self, query: str, params=None):
        raw_query = query.strip()
        lastrowid = None

        # Intercept SQLite PRAGMA table_info(<table>)
        pragma_match = re.match(r"^PRAGMA\s+table_info\((\w+)\)", raw_query, re.IGNORECASE)
        if pragma_match:
            table_name = pragma_match.group(1).lower()
            sql = (
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_name = %s ORDER BY ordinal_position"
            )
            cur = self._conn.cursor()
            cur.execute(sql, (table_name,))
            return PostgresCursorWrapper(cur)

        # Translate '?' to '%s'
        translated_sql = _translate_query(raw_query)

        # For INSERT statements without RETURNING, append RETURNING <pk> to capture lastrowid
        is_insert = re.match(r"^\s*INSERT\s+INTO\s+(\w+)", translated_sql, re.IGNORECASE)
        has_returning = re.search(r"\bRETURNING\b", translated_sql, re.IGNORECASE)

        cur = self._conn.cursor()
        try:
            if is_insert and not has_returning:
                table_name = is_insert.group(1).lower()
                pk_col = "user_id" if table_name == "user_progression" else "id"
                try_sql = f"{translated_sql.rstrip().rstrip(';')} RETURNING {pk_col};"
                cur.execute(try_sql, params or ())
                res = cur.fetchone()
                if res:
                    lastrowid = res[0]
                return PostgresCursorWrapper(cur, lastrowid=lastrowid)

            cur.execute(translated_sql, params or ())
            return PostgresCursorWrapper(cur, lastrowid=lastrowid)
        except psycopg2.IntegrityError as e:
            raise sqlite3.IntegrityError(str(e)) from e
        except psycopg2.OperationalError as e:
            raise sqlite3.OperationalError(str(e)) from e

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()


def connect():
    """
    Connects to the database.
    If NEON_DATABASE_URL or DATABASE_URL is set, connects to Neon PostgreSQL.
    Otherwise, connects to the local SQLite database (with /tmp fallback on Vercel).
    """
    if USE_POSTGRES:
        try:
            return PostgresConnectionWrapper(NEON_DATABASE_URL)
        except Exception as e:
            print(f"[FocusFlow DB] Warning: Failed to connect to Neon PostgreSQL ({e}). Falling back to SQLite.")

    # SQLite fallback
    db_path = _get_sqlite_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initializes database schema for either PostgreSQL or SQLite."""
    with connect() as db:
        if USE_POSTGRES:
            # PostgreSQL Schema
            db.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    gemini_api_key TEXT DEFAULT ''
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Study',
                    priority TEXT NOT NULL DEFAULT 'Medium',
                    due_date TEXT NOT NULL DEFAULT '',
                    estimated_minutes INTEGER NOT NULL DEFAULT 30,
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    user_id INTEGER REFERENCES users(id),
                    xp_awarded INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    duration_minutes INTEGER NOT NULL,
                    completed_at TEXT NOT NULL,
                    user_id INTEGER REFERENCES users(id),
                    xp_awarded INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS user_progression (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id),
                    total_xp INTEGER NOT NULL DEFAULT 0,
                    current_level INTEGER NOT NULL DEFAULT 1,
                    rank_tier TEXT NOT NULL DEFAULT 'Bronze',
                    current_streak INTEGER NOT NULL DEFAULT 0,
                    last_active_date TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS user_achievements (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    achievement_id TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    UNIQUE(user_id, achievement_id)
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS xp_transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    amount INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    reference_id TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, activity_type, reference_id)
                )"""
            )

            # Ensure columns exist in case of partial migrations
            user_cols = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
            if "gemini_api_key" not in user_cols:
                db.execute("ALTER TABLE users ADD COLUMN gemini_api_key TEXT DEFAULT ''")

            for table in ("tasks", "sessions"):
                cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
                if "user_id" not in cols:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")
                if "xp_awarded" not in cols:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN xp_awarded INTEGER NOT NULL DEFAULT 0")

            db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_xp_user ON xp_transactions(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_achieve_user ON user_achievements(user_id)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lower_email ON users (LOWER(email))")

        else:
            # SQLite Schema
            db.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Study',
                    priority TEXT NOT NULL DEFAULT 'Medium',
                    due_date TEXT NOT NULL DEFAULT '',
                    estimated_minutes INTEGER NOT NULL DEFAULT 30,
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    user_id INTEGER REFERENCES users(id),
                    xp_awarded INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    duration_minutes INTEGER NOT NULL,
                    completed_at TEXT NOT NULL,
                    user_id INTEGER REFERENCES users(id),
                    xp_awarded INTEGER NOT NULL DEFAULT 0
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS user_progression (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id),
                    total_xp INTEGER NOT NULL DEFAULT 0,
                    current_level INTEGER NOT NULL DEFAULT 1,
                    rank_tier TEXT NOT NULL DEFAULT 'Bronze',
                    current_streak INTEGER NOT NULL DEFAULT 0,
                    last_active_date TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS user_achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    achievement_id TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    UNIQUE(user_id, achievement_id)
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS xp_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    amount INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    reference_id TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, activity_type, reference_id)
                )"""
            )

            user_cols = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
            if "gemini_api_key" not in user_cols:
                db.execute("ALTER TABLE users ADD COLUMN gemini_api_key TEXT DEFAULT ''")

            for table in ("tasks", "sessions"):
                cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
                if "user_id" not in cols:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")
                if "xp_awarded" not in cols:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN xp_awarded INTEGER NOT NULL DEFAULT 0")

            db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_xp_user ON xp_transactions(user_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_achieve_user ON user_achievements(user_id)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lower_email ON users (LOWER(email))")

        db.commit()
