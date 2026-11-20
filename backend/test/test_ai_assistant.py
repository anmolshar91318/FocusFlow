import unittest
import json
from ai_assistant import (
    build_user_context,
    PREFERRED_LOW_CREDIT_MODELS,
    fetch_gemini_models,
)
from app import app, init_db, connect

class AIAssistantTestCase(unittest.TestCase):
    def setUp(self):
        import os
        self._orig_key = os.environ.pop("GEMINI_API_KEY", None)
        app.config["TESTING"] = True
        self.client = app.test_client()
        init_db()

    def tearDown(self):
        import os
        if self._orig_key:
            os.environ["GEMINI_API_KEY"] = self._orig_key
        else:
            os.environ.pop("GEMINI_API_KEY", None)

    def test_low_credit_model_preference(self):
        """Verifies flash models are prioritized for low credit consumption."""
        self.assertIn("gemini-1.5-flash-8b", PREFERRED_LOW_CREDIT_MODELS)
        self.assertIn("gemini-1.5-flash", PREFERRED_LOW_CREDIT_MODELS)
        self.assertIn("gemini-2.0-flash", PREFERRED_LOW_CREDIT_MODELS)

    def test_build_user_context(self):
        """Verifies user productivity data is correctly assembled for grounding."""
        with connect() as db:
            # Create user
            cur = db.execute("INSERT OR IGNORE INTO users(name, email, password_hash, created_at) VALUES ('ContextTester', 'context@test.com', 'hash', '2026-11-19')")
            uid = cur.lastrowid or db.execute("SELECT id FROM users WHERE email='context@test.com'").fetchone()["id"]
            
            # Insert a task
            db.execute("INSERT INTO tasks(title, priority, category, user_id, completed, created_at) VALUES ('Prepare for Algorithms Exam', 'High', 'Exam preparation', ?, 0, '2026-11-19')", (uid,))
            db.commit()

            context = build_user_context(db, uid)
            self.assertIn("ContextTester", context)
            self.assertIn("Prepare for Algorithms Exam", context)
            self.assertIn("High", context)
            self.assertIn("USER PRODUCTIVITY PROFILE", context)
            self.assertIn("ACTIVE PENDING TASKS", context)

    def test_ai_config_endpoint_without_key(self):
        """Verifies /api/ai/config handles empty key state gracefully."""
        # Register and log in
        email = f"ai_user_{id(self)}@test.com"
        self.client.post("/api/auth/register", json={"name": "AI Tester", "email": email, "password": "Password123"})
        
        res = self.client.get("/api/ai/config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("has_key", data)
        self.assertIn("recommended_model", data)

    def test_ai_chat_needs_key_notification(self):
        """Verifies chat informs user to configure API key when missing."""
        email = f"ai_chat_{id(self)}@test.com"
        self.client.post("/api/auth/register", json={"name": "Chat Tester", "email": email, "password": "Password123"})
        
        res = self.client.post("/api/ai/chat", json={
            "messages": [{"role": "user", "content": "What should I do first?"}]
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("needs_key"))
        self.assertIn("Gemini API Key", data.get("reply"))

if __name__ == "__main__":
    unittest.main()
