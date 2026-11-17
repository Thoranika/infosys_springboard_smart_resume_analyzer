"""Authentication, password hashing, validation, and session management tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import utils.database as db
from backend.auth import (
    change_user_password,
    get_current_user,
    is_user_logged_in,
    login_user,
    logout_user,
    register_user,
)


class TestAuthModule(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self._tmpdir.name, "test_auth.db")
        db.init_db()
        logout_user()

    def tearDown(self) -> None:
        logout_user()
        db.DB_PATH = self._orig_db_path
        self._tmpdir.cleanup()

    def test_registration_validation_and_duplicate_prevention(self) -> None:
        ok, msg = register_user("", "a@b.com", "Strong@123", "Strong@123")
        self.assertFalse(ok)
        self.assertIn("empty", msg.lower())

        ok, msg = register_user("John123", "a@b.com", "Strong@123", "Strong@123")
        self.assertFalse(ok)

        ok, msg = register_user("John Doe", "invalid-email", "Strong@123", "Strong@123")
        self.assertFalse(ok)

        ok, msg = register_user("John Doe", "john@example.com", "weak", "weak")
        self.assertFalse(ok)

        ok, msg = register_user("John Doe", "john@example.com", "Strong@123", "Different@123")
        self.assertFalse(ok)

        ok, msg = register_user("John Doe", "john@example.com", "Strong@123", "Strong@123")
        self.assertTrue(ok)

        # Duplicate check
        ok_dup, msg_dup = register_user("John Doe", "john@example.com", "Strong@123", "Strong@123")
        self.assertFalse(ok_dup)
        self.assertIn("already exists", msg_dup.lower())

        # Ensure password is hashed with bcrypt (not plain text)
        user_row = db.get_user_by_email("john@example.com")
        self.assertNotEqual(user_row["password_hash"], "Strong@123")
        self.assertTrue(user_row["password_hash"].startswith("$2"))

    def test_login_logout_and_password_change(self) -> None:
        register_user("Jane Roe", "jane@example.com", "Secure#2025", "Secure#2025")

        ok_bad, _ = login_user("jane@example.com", "WrongPass#1")
        self.assertFalse(ok_bad)
        self.assertFalse(is_user_logged_in())

        ok_good, _ = login_user("jane@example.com", "Secure#2025")
        self.assertTrue(ok_good)
        self.assertTrue(is_user_logged_in())
        curr = get_current_user()
        self.assertEqual(curr["email"], "jane@example.com")

        # Change password
        ok_chg, _ = change_user_password(curr["id"], "Secure#2025", "NewPass!99", "NewPass!99")
        self.assertTrue(ok_chg)

        logout_user()
        self.assertFalse(is_user_logged_in())
        ok_new, _ = login_user("jane@example.com", "NewPass!99")
        self.assertTrue(ok_new)


if __name__ == "__main__":
    unittest.main()
