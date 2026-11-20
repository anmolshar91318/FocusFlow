import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
import time
from datetime import datetime, timezone, timedelta
from app import app, init_db, connect

class EmailAuthTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key"
        self.client = app.test_client()
        init_db()

    def test_registration_and_verification_flow(self):
        timestamp = int(time.time() * 1000)
        email = f"verify_{timestamp}@example.com"
        password = "Password123!"

        # 1. Register -> Should require verification
        res = self.client.post("/api/auth/register", json={
            "name": "Verify User",
            "email": email,
            "password": password
        })
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "verification_required")

        # 2. Try logging in before verifying -> Should be rejected with 403 needs_verification
        login_unverified = self.client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        self.assertEqual(login_unverified.status_code, 403)
        self.assertTrue(login_unverified.get_json().get("needs_verification"))

        # 3. Retrieve code from DB
        with connect() as db:
            user = db.execute("SELECT verification_code FROM users WHERE email=?", (email,)).fetchone()
            code = user["verification_code"]
        self.assertEqual(len(code), 6)

        # 4. Attempt verify with wrong code -> 400
        bad_v = self.client.post("/api/auth/verify-email", json={
            "email": email,
            "code": "000000" if code != "000000" else "111111"
        })
        self.assertEqual(bad_v.status_code, 400)

        # 5. Verify with correct code -> 200 and logged in
        good_v = self.client.post("/api/auth/verify-email", json={
            "email": email,
            "code": code
        })
        self.assertEqual(good_v.status_code, 200)
        self.assertTrue(good_v.get_json()["user"]["is_verified"])

        # 6. Verify current_user works via session
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()["user"]["email"], email)

        # 7. Subsequent login succeeds
        self.client.post("/api/auth/logout")
        login_res = self.client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        self.assertEqual(login_res.status_code, 200)

    def test_resend_verification(self):
        timestamp = int(time.time() * 1000)
        email = f"resend_{timestamp}@example.com"
        self.client.post("/api/auth/register", json={
            "name": "Resend Tester",
            "email": email,
            "password": "Password123!"
        })

        with connect() as db:
            first_code = db.execute("SELECT verification_code FROM users WHERE email=?", (email,)).fetchone()["verification_code"]

        # Resend code
        res = self.client.post("/api/auth/resend-verification", json={"email": email})
        self.assertEqual(res.status_code, 200)

        with connect() as db:
            second_code = db.execute("SELECT verification_code FROM users WHERE email=?", (email,)).fetchone()["verification_code"]

        self.assertEqual(len(second_code), 6)

    def test_forgot_and_reset_password_flow(self):
        timestamp = int(time.time() * 1000)
        email = f"reset_{timestamp}@example.com"
        old_password = "OldPassword123!"
        new_password = "NewPassword456!"

        # Register and verify
        self.client.post("/api/auth/register", json={
            "name": "Password Reset User",
            "email": email,
            "password": old_password
        })
        with connect() as db:
            code = db.execute("SELECT verification_code FROM users WHERE email=?", (email,)).fetchone()["verification_code"]
        self.client.post("/api/auth/verify-email", json={"email": email, "code": code})
        self.client.post("/api/auth/logout")

        # Request forgot password
        forgot_res = self.client.post("/api/auth/forgot-password", json={"email": email})
        self.assertEqual(forgot_res.status_code, 200)

        with connect() as db:
            reset_code = db.execute("SELECT reset_code FROM users WHERE email=?", (email,)).fetchone()["reset_code"]
        self.assertEqual(len(reset_code), 6)

        # Attempt reset with wrong code -> 400
        bad_reset = self.client.post("/api/auth/reset-password", json={
            "email": email,
            "code": "999999",
            "new_password": new_password
        })
        self.assertEqual(bad_reset.status_code, 400)

        # Attempt reset with too short password -> 400
        short_reset = self.client.post("/api/auth/reset-password", json={
            "email": email,
            "code": reset_code,
            "new_password": "short"
        })
        self.assertEqual(short_reset.status_code, 400)

        # Reset with correct code
        good_reset = self.client.post("/api/auth/reset-password", json={
            "email": email,
            "code": reset_code,
            "new_password": new_password
        })
        self.assertEqual(good_reset.status_code, 200)

        # Old password should now fail
        old_login = self.client.post("/api/auth/login", json={
            "email": email,
            "password": old_password
        })
        self.assertEqual(old_login.status_code, 401)

        # New password should succeed
        new_login = self.client.post("/api/auth/login", json={
            "email": email,
            "password": new_password
        })
        self.assertEqual(new_login.status_code, 200)
        self.assertEqual(new_login.get_json()["user"]["email"], email)

if __name__ == "__main__":
    unittest.main()
