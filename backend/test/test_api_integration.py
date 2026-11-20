import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import json
from app import app, init_db, connect

class ApiIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret"
        self.client = app.test_client()
        init_db()

    def test_full_progression_flow(self):
        email = f"user_{datetime_now_str()}@test.com"
        # 1. Register
        res = self.client.post("/api/auth/register", json={
            "name": "Integration Tester",
            "email": email,
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 201)

        # 1b. Verify email
        with connect() as db:
            row = db.execute("SELECT verification_code FROM users WHERE email=?", (email,)).fetchone()
            code = row["verification_code"]
        v_res = self.client.post("/api/auth/verify-email", json={
            "email": email,
            "code": code
        })
        self.assertEqual(v_res.status_code, 200)

        # 2. Check initial progression
        res = self.client.get("/api/progression")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["progression"]
        self.assertEqual(data["total_xp"], 0)
        self.assertEqual(data["current_level"], 1)
        self.assertEqual(data["level_title"], "Beginner")
        self.assertEqual(data["rank_tier"], "Bronze")
        self.assertEqual(data["unlocked_achievements_count"], 0)

        # 3. Add task and complete it
        t_res = self.client.post("/api/tasks", json={
            "title": "Complete documentation",
            "category": "Project",
            "priority": "High",
            "estimated_minutes": 25
        })
        self.assertEqual(t_res.status_code, 201)
        task_id = t_res.get_json()["task"]["id"]

        # Complete task -> Expect 10 XP + Daily streak bonus 15 XP
        patch_res = self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})
        self.assertEqual(patch_res.status_code, 200)
        p_data = patch_res.get_json()
        self.assertEqual(p_data["xp_earned"], 10)
        # Streak bonus may be 15 XP
        self.assertGreaterEqual(p_data["progression"]["total_xp"], 10)
        # First task achievement unlocked!
        unlocked = [a["id"] for a in p_data["newly_unlocked_achievements"]]
        self.assertIn("first_task", unlocked)

        # 4. Anti-exploit: uncheck and re-check same task -> 0 XP!
        uncheck_res = self.client.patch(f"/api/tasks/{task_id}", json={"completed": False})
        self.assertEqual(uncheck_res.get_json()["xp_earned"], 0)

        recheck_res = self.client.patch(f"/api/tasks/{task_id}", json={"completed": True})
        self.assertEqual(recheck_res.get_json()["xp_earned"], 0)

        # 5. Complete 25-minute focus session
        s_res = self.client.post("/api/sessions", json={"duration_minutes": 25})
        self.assertEqual(s_res.status_code, 201)
        s_data = s_res.get_json()
        self.assertEqual(s_data["xp_earned"], 25)
        # First focus achievement unlocked!
        s_unlocked = [a["id"] for a in s_data["newly_unlocked_achievements"]]
        self.assertIn("first_focus", s_unlocked)

        # 6. Verify progression endpoint reflects the new XP and stats
        res2 = self.client.get("/api/progression")
        self.assertEqual(res2.status_code, 200)
        p2 = res2.get_json()["progression"]
        self.assertEqual(p2["total_sessions"], 1)
        self.assertEqual(p2["completed_tasks"], 1)
        self.assertGreaterEqual(p2["unlocked_achievements_count"], 2)

def datetime_now_str():
    import time
    return str(int(time.time() * 1000))

if __name__ == "__main__":
    unittest.main()
