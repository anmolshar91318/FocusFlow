import os
import re
from pathlib import Path

# Load environment variables from backend/.env or root .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    for p in [Path(__file__).with_name(".env"), Path(__file__).parent.parent / ".env"]:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass

try:
    import psycopg2
    import psycopg2.extras
    IntegrityError = psycopg2.IntegrityError
    OperationalError = psycopg2.OperationalError
    DatabaseError = psycopg2.DatabaseError
    DataError = psycopg2.DataError
except ImportError:
    psycopg2 = None

    class IntegrityError(Exception):
        pass

    class OperationalError(Exception):
        pass

    class DatabaseError(Exception):
        pass

    class DataError(Exception):
        pass


def get_neon_database_url() -> str:
    """Retrieves and sanitizes Neon PostgreSQL connection URL."""
    url = (
        os.environ.get("NEON_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or ""
    ).strip()

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    if url and "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"

    return url


# Flag indicating whether Neon PostgreSQL is configured
USE_POSTGRES = True


class DictLikeRow:
    """Provides dictionary and index access for PostgreSQL query results."""

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
    """Translates SQL query with '?' parameter markers to PostgreSQL '%s'."""
    parts = []
    tokens = re.split(r"('(?:''|[^'])*')", query)
    for i, token in enumerate(tokens):
        if i % 2 == 1:
            parts.append(token)
        else:
            parts.append(token.replace("?", "%s"))
    return "".join(parts)


class PostgresCursorWrapper:
    """Wraps psycopg2 cursor with dict-like row access and lastrowid support."""

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
    """Connection wrapper for Neon PostgreSQL."""

    def __init__(self, dsn):
        self._dsn = dsn
        self._conn = psycopg2.connect(dsn)

    def execute(self, query: str, params=None):
        raw_query = query.strip()
        lastrowid = None

        # Intercept table info queries to read from PostgreSQL information_schema
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
    Connects directly to Neon PostgreSQL.
    Raises RuntimeError if NEON_DATABASE_URL is not configured.
    """
    if psycopg2 is None:
        raise ImportError(
            "psycopg2 is required to connect to Neon PostgreSQL. "
            "Please install it with: pip install psycopg2-binary"
        )

    dsn = get_neon_database_url()
    if not dsn:
        raise RuntimeError(
            "NEON_DATABASE_URL is not configured. FocusFlow connects exclusively to Neon PostgreSQL. "
            "Please set NEON_DATABASE_URL in backend/.env "
            "(e.g., NEON_DATABASE_URL=postgresql://user:password@ep-xyz.aws.neon.tech/neondb?sslmode=require)."
        )

    return PostgresConnectionWrapper(dsn)


def init_database():
    """Initializes the Neon PostgreSQL schema, tables, and indexes."""
    with connect() as db:
        # Neon PostgreSQL Schema
        db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                gemini_api_key TEXT DEFAULT '',
                is_verified INTEGER NOT NULL DEFAULT 0,
                verification_code TEXT DEFAULT '',
                verification_code_expires_at TEXT DEFAULT '',
                reset_code TEXT DEFAULT '',
                reset_code_expires_at TEXT DEFAULT ''
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
        if "is_verified" not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
            db.execute("UPDATE users SET is_verified = 1 WHERE is_verified IS NULL OR is_verified = 0")
        if "verification_code" not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN verification_code TEXT DEFAULT ''")
        if "verification_code_expires_at" not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN verification_code_expires_at TEXT DEFAULT ''")
        if "reset_code" not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN reset_code TEXT DEFAULT ''")
        if "reset_code_expires_at" not in user_cols:
            db.execute("ALTER TABLE users ADD COLUMN reset_code_expires_at TEXT DEFAULT ''")

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
