"""
Comprehensive End-to-End Verification Test for FocusFlow Gamification,
Leveling, Rewards and Achievement System.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import json
from datetime import datetime, timezone, timedelta
from app import app, init_db, connect
from gamification import (
    calculate_level,
    calculate_rank,
    calculate_session_xp,
    total_xp_for_level,
    ACHIEVEMENTS_CATALOG,
    XP_PER_TASK,
    XP_DAILY_STREAK,
    XP_WEEKLY_GOAL,
)

class E2EGamificationTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        init_db()

    def register_and_verify(self, name, email, password):
        self.client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
        with connect() as db:
            row = db.execute("SELECT verification_code FROM users WHERE email=?", (email,)).fetchone()
            code = row["verification_code"]
        res = self.client.post("/api/auth/verify-email", json={"email": email, "code": code})
        return res.get_json()["user"]

    def test_multi_user_isolation_and_xp_accuracy(self):
        """Tests that two separate users have isolated progression and stats."""
        u1_email = f"user_alpha_{int(datetime.now().timestamp() * 1000)}@test.com"
        u2_email = f"user_beta_{int(datetime.now().timestamp() * 1000)}@test.com"

        # Register User 1
        u1 = self.register_and_verify("Alpha User", u1_email, "Password123")
        u1_id = u1["id"]

        # User 1: complete 25m session
        s1 = self.client.post("/api/sessions", json={"duration_minutes": 25})
        self.assertEqual(s1.status_code, 201)
        s1_data = s1.get_json()
        self.assertEqual(s1_data["xp_earned"], 25)

        # Check User 1 progression
        p1 = self.client.get("/api/progression").get_json()["progression"]
        u1_xp = p1["total_xp"]
        self.assertGreaterEqual(u1_xp, 25)

        # Log out
        self.client.post("/api/auth/logout")

        # Register User 2
        u2 = self.register_and_verify("Beta User", u2_email, "Password123")
        u2_id = u2["id"]

        # Check User 2 initial progression (must be 0, completely isolated from User 1)
        p2 = self.client.get("/api/progression").get_json()["progression"]
        self.assertEqual(p2["total_xp"], 0)
        self.assertEqual(p2["total_sessions"], 0)
        self.assertEqual(p2["current_level"], 1)

        # User 2: complete 50m session
        s2 = self.client.post("/api/sessions", json={"duration_minutes": 50})
        self.assertEqual(s2.status_code, 201)
        self.assertEqual(s2.get_json()["xp_earned"], 50)

        # User 2 progression
        p2_updated = self.client.get("/api/progression").get_json()["progression"]
        self.assertGreaterEqual(p2_updated["total_xp"], 50)
        self.assertEqual(p2_updated["total_sessions"], 1)
        self.assertEqual(p2_updated["total_focus_minutes"], 50)

        # Log back in as User 1 and verify User 1's progress was undisturbed
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"email": u1_email, "password": "Password123"})
        p1_restored = self.client.get("/api/progression").get_json()["progression"]
        self.assertEqual(p1_restored["total_xp"], u1_xp)
        self.assertEqual(p1_restored["total_sessions"], 1)
        self.assertEqual(p1_restored["total_focus_minutes"], 25)

    def test_duplicate_prevention_on_tasks(self):
        """Tests that toggling task completion does NOT grant repeated XP."""
        email = f"task_test_{int(datetime.now().timestamp() * 1000)}@test.com"
        self.register_and_verify("Task Tester", email, "Password123")

        t_res = self.client.post("/api/tasks", json={"title": "Anti-exploit task", "priority": "High"})
        task_id = t_res.get_json()["task"]["id"]

        # First completion: awards 10 XP
        c1 = self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})
        self.assertEqual(c1.get_json()["xp_earned"], 10)
        xp_after_first = c1.get_json()["progression"]["total_xp"]

        # Uncheck task
        c2 = self.client.patch(f"/api/tasks/{task_id}", json={"completed": False})
        self.assertEqual(c2.get_json()["xp_earned"], 0)

        # Re-check task: should award 0 XP
        c3 = self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})
        self.assertEqual(c3.get_json()["xp_earned"], 0)
        xp_after_recheck = c3.get_json()["progression"]["total_xp"]
        self.assertEqual(xp_after_first, xp_after_recheck)

    def test_level_progression_curve(self):
        """Verifies level progression formula up to Level 30."""
        # Level 1: Beginner
        self.assertEqual(calculate_level(0)["title"], "Beginner")
        self.assertEqual(calculate_level(99)["level"], 1)
        
        # Level 2: Getting Started (at 100 XP)
        self.assertEqual(calculate_level(100)["level"], 2)
        self.assertEqual(calculate_level(100)["title"], "Getting Started")
        
        # Level 3: Focus Explorer (at 250 XP)
        self.assertEqual(calculate_level(250)["level"], 3)
        self.assertEqual(calculate_level(250)["title"], "Focus Explorer")

        # Level 5: Productivity Enthusiast (at 700 XP)
        self.assertEqual(calculate_level(700)["level"], 5)
        self.assertEqual(calculate_level(700)["title"], "Productivity Enthusiast")

        # Level 10: Focus Master (at 2700 XP)
        self.assertEqual(calculate_level(2700)["level"], 10)
        self.assertEqual(calculate_level(2700)["title"], "Focus Master")

        # Level 20: Productivity Champion (at 10450 XP)
        self.assertEqual(calculate_level(10450)["level"], 20)
        self.assertEqual(calculate_level(10450)["title"], "Productivity Champion")

        # Level 30: Elite Performer (at 23200 XP)
        self.assertEqual(calculate_level(23200)["level"], 30)
        self.assertEqual(calculate_level(23200)["title"], "Elite Performer")

    def test_rank_progression(self):
        """Verifies rank tiers from Bronze to Master."""
        self.assertEqual(calculate_rank(100)["name"], "Bronze")
        self.assertEqual(calculate_rank(500)["name"], "Silver")
        self.assertEqual(calculate_rank(1500)["name"], "Gold")
        self.assertEqual(calculate_rank(3500)["name"], "Platinum")
        self.assertEqual(calculate_rank(7000)["name"], "Diamond")
        self.assertEqual(calculate_rank(12000)["name"], "Master")

    def test_achievements_catalog_completeness(self):
        """Verifies all required achievements exist in the catalog."""
        catalog_ids = {a["id"] for a in ACHIEVEMENTS_CATALOG}
        required_achievements = {
            "first_focus",
            "deep_worker",
            "focus_champion",
            "consistency_king",
            "task_master",
            "early_bird",
            "marathon_worker",
            "first_task",
            "high_priority_striker",
            "night_owl",
            "streak_starter",
            "focus_master",
        }
        for req in required_achievements:
            self.assertIn(req, catalog_ids, f"Missing achievement: {req}")

if __name__ == "__main__":
    unittest.main()
