import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import sqlite3
from datetime import datetime, timezone, timedelta
from gamification import (
    calculate_level,
    calculate_rank,
    calculate_session_xp,
    total_xp_for_level,
    xp_required_for_next_level,
    get_or_init_progression,
    award_xp,
    compute_current_streak,
    update_user_streak_and_award_bonus,
    check_weekly_focus_goal_bonus,
    check_and_unlock_achievements,
    get_user_progression_summary,
    XP_PER_TASK,
    XP_DAILY_STREAK,
    XP_WEEKLY_GOAL,
)
from database import IntegrityError

class TestDbWrapper:
    def __init__(self, conn):
        self._conn = conn
    def execute(self, *args, **kwargs):
        try:
            return self._conn.execute(*args, **kwargs)
        except sqlite3.IntegrityError as e:
            raise IntegrityError(str(e)) from e
    def commit(self):
        return self._conn.commit()
    def close(self):
        return self._conn.close()

class GamificationTestCase(unittest.TestCase):
    def setUp(self):
        raw_db = sqlite3.connect(":memory:")
        raw_db.row_factory = sqlite3.Row
        raw_db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
        raw_db.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT, category TEXT, priority TEXT, due_date TEXT, estimated_minutes INTEGER, completed INTEGER, created_at TEXT, user_id INTEGER, xp_awarded INTEGER DEFAULT 0)")
        raw_db.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, duration_minutes INTEGER, completed_at TEXT, user_id INTEGER, xp_awarded INTEGER DEFAULT 0)")
        raw_db.execute("CREATE TABLE user_progression (user_id INTEGER PRIMARY KEY, total_xp INTEGER DEFAULT 0, current_level INTEGER DEFAULT 1, rank_tier TEXT DEFAULT 'Bronze', current_streak INTEGER DEFAULT 0, last_active_date TEXT DEFAULT '', updated_at TEXT)")
        raw_db.execute("CREATE TABLE user_achievements (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, achievement_id TEXT, unlocked_at TEXT, UNIQUE(user_id, achievement_id))")
        raw_db.execute("CREATE TABLE xp_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, activity_type TEXT, reference_id TEXT DEFAULT '', description TEXT, created_at TEXT, UNIQUE(user_id, activity_type, reference_id))")
        
        # Insert test user
        raw_db.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@test.com')")
        raw_db.commit()
        self.db = TestDbWrapper(raw_db)

    def tearDown(self):
        self.db.close()

    def test_level_formula(self):
        self.assertEqual(total_xp_for_level(1), 0)
        self.assertEqual(total_xp_for_level(2), 100)
        self.assertEqual(total_xp_for_level(3), 250)
        self.assertEqual(total_xp_for_level(5), 700)
        self.assertEqual(total_xp_for_level(10), 2700)

        # Level calculation
        l1 = calculate_level(50)
        self.assertEqual(l1["level"], 1)
        self.assertEqual(l1["title"], "Beginner")
        self.assertEqual(l1["current_level_xp"], 50)
        self.assertEqual(l1["next_level_xp"], 100)
        self.assertEqual(l1["progress_percent"], 50)

        l2 = calculate_level(100)
        self.assertEqual(l2["level"], 2)
        self.assertEqual(l2["title"], "Getting Started")
        self.assertEqual(l2["current_level_xp"], 0)

        l5 = calculate_level(750)
        self.assertEqual(l5["level"], 5)
        self.assertEqual(l5["title"], "Productivity Enthusiast")

        l10 = calculate_level(2700)
        self.assertEqual(l10["level"], 10)
        self.assertEqual(l10["title"], "Focus Master")

    def test_rank_formula(self):
        self.assertEqual(calculate_rank(0)["name"], "Bronze")
        self.assertEqual(calculate_rank(499)["name"], "Bronze")
        self.assertEqual(calculate_rank(500)["name"], "Silver")
        self.assertEqual(calculate_rank(1500)["name"], "Gold")
        self.assertEqual(calculate_rank(3500)["name"], "Platinum")
        self.assertEqual(calculate_rank(7000)["name"], "Diamond")
        self.assertEqual(calculate_rank(12000)["name"], "Master")

    def test_session_xp(self):
        self.assertEqual(calculate_session_xp(25), 25)
        self.assertEqual(calculate_session_xp(50), 50)
        self.assertEqual(calculate_session_xp(2), 0)  # Under 5 mins gets 0
        self.assertEqual(calculate_session_xp(45), 45)

    def test_award_xp_and_duplicate_prevention(self):
        res1 = award_xp(self.db, 1, 25, "session", "session:1", "25m session")
        self.assertTrue(res1["awarded"])
        self.assertEqual(res1["amount"], 25)
        self.assertEqual(res1["total_xp"], 25)

        # Duplicate attempt with same reference_id
        res2 = award_xp(self.db, 1, 25, "session", "session:1", "25m session duplicate")
        self.assertFalse(res2["awarded"])
        self.assertTrue(res2.get("duplicate"))

        # Verify DB total is still 25
        prog = get_or_init_progression(self.db, 1)
        self.assertEqual(prog["total_xp"], 25)

    def test_level_up_detection(self):
        # Award 90 XP
        res1 = award_xp(self.db, 1, 90, "session", "session:1", "Long session")
        self.assertFalse(res1["leveled_up"])
        self.assertEqual(res1["new_level"], 1)

        # Award 20 XP more (total 110 XP -> Level 2)
        res2 = award_xp(self.db, 1, 20, "session", "session:2", "Second session")
        self.assertTrue(res2["leveled_up"])
        self.assertEqual(res2["old_level"], 1)
        self.assertEqual(res2["new_level"], 2)
        self.assertEqual(res2["new_title"], "Getting Started")

    def test_achievements_unlocking(self):
        # Add a session of 25m
        self.db.execute("INSERT INTO sessions VALUES (1, 25, '2026-11-19T10:00:00', 1, 1)")
        self.db.commit()

        unlocked = check_and_unlock_achievements(self.db, 1)
        unlocked_ids = [a["id"] for a in unlocked]
        self.assertIn("first_focus", unlocked_ids)

        # Calling again should not re-unlock
        unlocked_again = check_and_unlock_achievements(self.db, 1)
        self.assertEqual(len(unlocked_again), 0)

    def test_marathon_and_time_achievements(self):
        # 50 min session at 07:15 AM
        self.db.execute("INSERT INTO sessions VALUES (2, 50, '2026-11-19T07:15:00', 1, 1)")
        self.db.commit()

        unlocked = check_and_unlock_achievements(self.db, 1)
        unlocked_ids = [a["id"] for a in unlocked]
        self.assertIn("marathon_worker", unlocked_ids)
        self.assertIn("early_bird", unlocked_ids)

    def test_streak_calculation_and_daily_bonus(self):
        today = datetime.now(timezone.utc).date()
        d0 = today.isoformat()
        d1 = (today - timedelta(days=1)).isoformat()
        d2 = (today - timedelta(days=2)).isoformat()

        # Insert sessions across 3 consecutive days
        self.db.execute("INSERT INTO sessions VALUES (10, 25, ?, 1, 1)", (f"{d2}T12:00:00",))
        self.db.execute("INSERT INTO sessions VALUES (11, 25, ?, 1, 1)", (f"{d1}T12:00:00",))
        self.db.execute("INSERT INTO sessions VALUES (12, 25, ?, 1, 1)", (f"{d0}T12:00:00",))
        self.db.commit()

        streak = compute_current_streak(self.db, 1)
        self.assertEqual(streak, 3)

        # Award daily streak bonus
        res1 = update_user_streak_and_award_bonus(self.db, 1)
        self.assertEqual(res1["streak"], 3)
        self.assertEqual(res1["bonus_xp"], XP_DAILY_STREAK)

        # Second call on same day should NOT award double bonus
        res2 = update_user_streak_and_award_bonus(self.db, 1)
        self.assertEqual(res2["bonus_xp"], 0)

    def test_weekly_goal_bonus(self):
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        # Add sessions totaling 125 mins this week
        self.db.execute("INSERT INTO sessions VALUES (20, 50, ?, 1, 1)", (now_iso,))
        self.db.execute("INSERT INTO sessions VALUES (21, 50, ?, 1, 1)", (now_iso,))
        self.db.execute("INSERT INTO sessions VALUES (22, 25, ?, 1, 1)", (now_iso,))
        self.db.commit()

        res1 = check_weekly_focus_goal_bonus(self.db, 1)
        self.assertTrue(res1["awarded"])
        self.assertEqual(res1["xp"], XP_WEEKLY_GOAL)

        # Second check in same week -> no duplicate
        res2 = check_weekly_focus_goal_bonus(self.db, 1)
        self.assertFalse(res2["awarded"])

    def test_summary_payload(self):
        summary = get_user_progression_summary(self.db, 1)
        self.assertIn("total_xp", summary)
        self.assertIn("current_level", summary)
        self.assertIn("rank_tier", summary)
        self.assertIn("achievements", summary)
        self.assertEqual(len(summary["achievements"]), 12)

if __name__ == "__main__":
    unittest.main()
