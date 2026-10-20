"""
tests/test_storage.py - Tests for SQLite repository, transactions, failure isolation, and JSON file migration.
"""

import os
import json
import tempfile
import unittest
from datetime import datetime, timezone

from app.models import (
    UserKey,
    Draft,
    GenerationRequest,
    SavedScript,
    ScriptPlan,
    Scene,
    EvidenceRecord,
    Idea,
)
from app.storage import Storage

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_bot.sqlite3")
        self.storage = Storage(db_path=self.db_path)
        self.user = UserKey(chat_id=111, user_id=222)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_settings_save_and_get(self):
        # Default settings
        settings = self.storage.get_settings(self.user)
        self.assertEqual(settings["duration"], "60 វិនាទី")
        self.assertAlmostEqual(settings["pace"], 10.0)

        # Custom settings
        self.storage.save_settings(self.user, "120 វិនាទី", 22.5)
        updated = self.storage.get_settings(self.user)
        self.assertEqual(updated["duration"], "120 វិនាទី")
        self.assertAlmostEqual(updated["pace"], 22.5)

    def test_draft_crud(self):
        draft = Draft(
            id="draft_123",
            revision=1,
            format_id="3whs",
            topic="Coding with AI",
            duration_seconds=60,
            audience="Programmers",
            comedy_style=None,
            actor_count=None,
            evidence_ids=["ev_1"],
            current_step="review",
        )
        self.storage.save_draft(self.user, draft)

        retrieved = self.storage.get_draft("draft_123")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "draft_123")
        self.assertEqual(retrieved.revision, 1)
        self.assertEqual(retrieved.format_id, "3whs")
        self.assertEqual(retrieved.topic, "Coding with AI")
        self.assertEqual(retrieved.evidence_ids, ["ev_1"])

    def test_save_successful_script_and_pointer_atomic_transaction(self):
        draft = Draft(
            id="draft_1",
            revision=1,
            format_id="3whs",
            topic="AI Tips",
            duration_seconds=60,
            audience="All",
        )
        req = GenerationRequest(
            id="req_100",
            operation="create",
            owner=self.user,
            draft_snapshot=draft.to_snapshot(),
            pace_units_per_second=18.0,
        )
        scene = Scene(
            scene_number=1,
            start_seconds=0,
            end_seconds=60,
            spoken_text_km="សួស្តីអ្នកទាំងអស់គ្នា",
            shot_size="Medium",
            camera_action="Static",
            visual_action="Smiling",
            on_screen_text_km="Tips",
            editing_note="None",
            audio_note="Upbeat",
        )
        plan = ScriptPlan(
            title="AI Tips",
            target_audience="All",
            hook="Hook text",
            caption="Caption text",
            hashtags=["#ai"],
            cta="Subscribe",
            target_duration_seconds=60,
            estimated_speaking_seconds=50.0,
            scenes=[scene],
        )
        script = SavedScript(
            id="script_200",
            version=1,
            owner=self.user,
            request_snapshot=req,
            plan=plan,
            created_at=datetime.now(timezone.utc),
        )

        # Save script transactionally
        self.storage.save_successful_script(script)

        # Verify script retrieval
        fetched = self.storage.get_script("script_200", 1)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, "script_200")
        self.assertEqual(fetched.plan.title, "AI Tips")
        self.assertEqual(len(fetched.plan.scenes), 1)

        # Verify pointer updated to this script
        last = self.storage.get_last_successful_script(self.user)
        self.assertIsNotNone(last)
        self.assertEqual(last.id, "script_200")
        self.assertEqual(last.version, 1)

    def test_failed_request_does_not_replace_last_successful_script(self):
        # 1. Save an initial successful script
        draft = Draft(id="d_ok", revision=1, format_id="3whs", topic="Good Topic", duration_seconds=60, audience="All")
        req = GenerationRequest(id="req_ok", operation="create", owner=self.user, draft_snapshot=draft.to_snapshot(), pace_units_per_second=18.0)
        plan = ScriptPlan(title="Good", target_audience="", hook="", caption="", hashtags=[], cta="", target_duration_seconds=60, estimated_speaking_seconds=40.0, scenes=[])
        script = SavedScript(id="s_ok", version=1, owner=self.user, request_snapshot=req, plan=plan, created_at=datetime.now(timezone.utc))
        self.storage.save_successful_script(script)

        # 2. Record a failed generation request
        fail_draft = Draft(id="d_fail", revision=1, format_id="3whs", topic="Bad Topic", duration_seconds=60, audience="All")
        fail_req = GenerationRequest(id="req_fail", operation="create", owner=self.user, draft_snapshot=fail_draft.to_snapshot(), pace_units_per_second=18.0)
        self.storage.save_failed_request(self.user, fail_req, error_code="INVALID_TIMELINE", user_message_km="Overlap")

        # 3. Last successful script MUST STILL be s_ok
        last_success = self.storage.get_last_successful_script(self.user)
        self.assertIsNotNone(last_success)
        self.assertEqual(last_success.id, "s_ok")
        self.assertEqual(last_success.plan.title, "Good")

        # 4. Failed request is retrievable for Retry
        last_failed = self.storage.get_last_failed_request(self.user)
        self.assertIsNotNone(last_failed)
        req, err, msg = last_failed
        self.assertEqual(req.id, "req_fail")
        self.assertEqual(req.draft_snapshot["topic"], "Bad Topic")
        self.assertEqual(err, "INVALID_TIMELINE")

    def test_subscriptions_toggle(self):
        self.assertFalse(self.storage.is_subscribed(self.user))
        self.assertEqual(len(self.storage.get_active_subscribers()), 0)

        # Enable subscription
        self.storage.set_subscription(self.user, True)
        self.assertTrue(self.storage.is_subscribed(self.user))
        subs = self.storage.get_active_subscribers()
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0], self.user)

        # Disable subscription
        self.storage.set_subscription(self.user, False)
        self.assertFalse(self.storage.is_subscribed(self.user))
        self.assertEqual(len(self.storage.get_active_subscribers()), 0)

    def test_json_file_migration(self):
        """Safely migrates user_settings.json and subscribers.json once without data loss."""
        mig_dir = tempfile.TemporaryDirectory()
        mig_db = os.path.join(mig_dir.name, "mig_test.sqlite3")
        settings_file = os.path.join(mig_dir.name, "user_settings.json")
        subs_file = os.path.join(mig_dir.name, "subscribers.json")

        # Create old json files
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump({
                "12345": {"duration": "180 វិនាទី", "pace": 20.0},
                "67890": {"duration": "300 វិនាទី", "pace": 16.5},
            }, f)

        with open(subs_file, "w", encoding="utf-8") as f:
            json.dump([12345, 99999], f)

        # Initialize storage pointing to legacy files
        storage = Storage(db_path=mig_db, legacy_settings_path=settings_file, legacy_subs_path=subs_file)

        # Verify migration of settings
        s1 = storage.get_settings(UserKey(12345, 12345))
        self.assertEqual(s1["duration"], "180 វិនាទី")
        self.assertEqual(s1["pace"], 20.0)

        s2 = storage.get_settings(UserKey(67890, 67890))
        self.assertEqual(s2["duration"], "300 វិនាទី")
        self.assertEqual(s2["pace"], 16.5)

        # Verify migration of subscriptions
        self.assertTrue(storage.is_subscribed(UserKey(12345, 12345)))
        self.assertTrue(storage.is_subscribed(UserKey(99999, 99999)))
        self.assertFalse(storage.is_subscribed(UserKey(67890, 67890)))

        # Verify original files remain preserved
        self.assertTrue(os.path.exists(settings_file))
        self.assertTrue(os.path.exists(subs_file))

        mig_dir.cleanup()

if __name__ == "__main__":
    unittest.main()
