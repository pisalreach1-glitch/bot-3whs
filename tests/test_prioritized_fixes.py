"""
tests/test_prioritized_fixes.py - Verification tests for all 8 prioritized ChatGPT review issues.

Covers:
- Red 1: Menu handles edit_top, edit_dur, and edit_failed callbacks
- Red 2: Home button cancels active in-flight request
- Red 3: Evidence records are retrieved from storage and attached to generation prompt
- Red 4: safe_edit cleanly splits long messages (>4000) and recovers from Markdown errors
- Orange 5: Daily ideas caching (Asia/Phnom_Penh) and locking prevent duplicate AI calls
- Orange 6: Refinement failure saves and passes valid request_id for retry (not script_id)
- Orange 7: Hook generation uses TaskManager to prevent concurrent / duplicate clicks
- Orange 8: Draft callbacks verify draft.owner to prevent cross-user actions in group chats
"""

import json
import tempfile
import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import (
    UserKey,
    Draft,
    GenerationRequest,
    SavedScript,
    GenerationResult,
    EvidenceRecord,
    Idea,
    ErrorCodes,
)
from app.storage import Storage
from app.task_manager import TaskManager
from app.navigation import navigation, Screens
from app.callbacks import encode_menu, encode_nav, encode_format, encode_duration, encode_generate, encode_script_action
from app.handlers.menu import handle_menu_callback
from app.handlers.creation import (
    handle_format_callback,
    handle_draft_duration_callback,
    handle_generate_callback,
    handle_retry_callback,
)
from app.handlers.comedy import handle_comedy_callback
from app.handlers.scripts import handle_script_action_callback
from app.telegram_io import split_message, safe_edit
from app.services.ideas import get_or_generate_ideas, clear_daily_ideas_cache, _DAILY_IDEAS_CACHE
from app.services.refinements import shorten_script, regenerate_script
from script_models import ScriptPlan, Scene

class TestPrioritizedFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_fixes.sqlite3"
        self.storage = Storage(db_path=self.db_path)
        self.task_mgr = TaskManager()
        self.user = UserKey(chat_id=100, user_id=200)
        self.other_user = UserKey(chat_id=100, user_id=999)
        navigation.clear()
        clear_daily_ideas_cache()

    def tearDown(self):
        self.temp_dir.cleanup()
        clear_daily_ideas_cache()

    def _make_mock_update(self, data: str, user_key: UserKey):
        update = MagicMock()
        query = MagicMock()
        query.data = data
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        msg = MagicMock()
        msg.reply_text = AsyncMock(return_value=MagicMock(edit_text=AsyncMock(), reply_text=AsyncMock()))
        query.message = msg
        update.callback_query = query
        update.effective_chat.id = user_key.chat_id
        update.effective_user.id = user_key.user_id
        update.message = None
        return update, query

    def _make_mock_context(self, ai_mock=None):
        ctx = MagicMock()
        ctx.bot_data = {
            "storage": self.storage,
            "task_mgr": self.task_mgr,
            "ai": ai_mock or MagicMock(),
        }
        return ctx

    # ── RED 1: Menu handles edit_top, edit_dur, and edit_failed ─────────
    def test_red_1_menu_edit_actions(self):
        async def run_test():
            draft = Draft(
                id="d_test_red1",
                revision=1,
                format_id="3whs",
                topic="ប្រធានបទដើម",
                duration_seconds=60,
                audience="អ្នកទស្សនា",
                owner=self.user,
            )
            self.storage.save_draft(self.user, draft)

            ctx = self._make_mock_context()

            # 1. edit_top
            upd1, q1 = self._make_mock_update(f"m:edit_top:{draft.id}", self.user)
            await handle_menu_callback(upd1, ctx)
            q1.edit_message_text.assert_called_once()
            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.TOPIC_INPUT)

            # 2. edit_dur
            upd2, q2 = self._make_mock_update(f"m:edit_dur:{draft.id}", self.user)
            await handle_menu_callback(upd2, ctx)
            q2.edit_message_text.assert_called_once()
            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.DRAFT_DURATION)

            # 3. edit_failed
            req = GenerationRequest(
                id="req_failed_1",
                operation="create",
                owner=self.user,
                draft_snapshot=draft.to_dict(),
                pace_units_per_second=10.0,
            )
            self.storage.save_failed_request(self.user, req, ErrorCodes.TIMEOUT, "Timeout error")

            upd3, q3 = self._make_mock_update("m:edit_failed:req_failed_1", self.user)
            await handle_menu_callback(upd3, ctx)
            q3.edit_message_text.assert_called_once()
            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.DRAFT_REVIEW)

        asyncio.run(run_test())

    # ── RED 2: Home button cancels active request ────────────────────────
    def test_red_2_home_cancels_running_request(self):
        async def run_test():
            token = await self.task_mgr.start_request(self.user, "active_req_123")
            self.assertTrue(self.task_mgr.is_current_request(self.user, token))

            ctx = self._make_mock_context()
            upd, q = self._make_mock_update("n:home", self.user)
            await handle_menu_callback(upd, ctx)

            # Assert task was cancelled!
            self.assertFalse(self.task_mgr.is_current_request(self.user, token))
            self.assertEqual(navigation.get_state(self.user).current_screen, Screens.HOME)

        asyncio.run(run_test())

    # ── RED 3: Evidence records loaded in handle_generate_callback ───────
    def test_red_3_evidence_loaded_in_generate_callback(self):
        async def run_test():
            ev = EvidenceRecord(
                id="ev_01",
                url="https://news.com/item1",
                platform_or_feed="news_rss",
                publisher="DAP News",
                retrieved_at=datetime.now(timezone.utc),
                title="កម្ពុជាជំរុញការវិនិយោគឌីជីថល",
            )
            # Save batch with evidence
            self.storage.save_idea_batch("b_batch_1", self.user, "tech", [], [ev])

            # Create draft referencing this evidence
            draft = Draft(
                id="d_sourced_1",
                revision=1,
                format_id="3whs",
                topic="បច្ចេកវិទ្យាឌីជីថល",
                duration_seconds=60,
                audience="សាធារណៈជន",
                evidence_ids=["ev_01"],
                owner=self.user,
            )
            self.storage.save_draft(self.user, draft)

            # Mock AI service to check prompt contains evidence
            received_prompt = []
            ai_mock = MagicMock()
            ai_mock._is_error_response = MagicMock(return_value=False)
            async def mock_gen(prompt, is_json=False):
                received_prompt.append(prompt)
                return json.dumps({
                    "title": "Script Sourced",
                    "target_audience": "Audience",
                    "hook": "Hook Sourced",
                    "caption": "Caption Sourced",
                    "hashtags": ["#tech"],
                    "cta": "Share",
                    "scenes": [
                        {
                            "scene_number": 1,
                            "start_seconds": 0,
                            "end_seconds": 60,
                            "spoken_text_km": "សួស្តីបងប្អូនទាំងអស់គ្នា",
                            "shot_size": "Medium Shot",
                            "camera_action": "Static",
                            "visual_action": "Action",
                            "on_screen_text_km": "Text",
                            "editing_note": "Note",
                            "audio_note": "Audio",
                        }
                    ]
                })
            ai_mock.generate_response = AsyncMock(side_effect=mock_gen)

            ctx = self._make_mock_context(ai_mock)
            upd, q = self._make_mock_update(f"g:{draft.id}:1", self.user)
            await handle_generate_callback(upd, ctx)

            self.assertTrue(len(received_prompt) > 0)
            self.assertIn("DAP News", received_prompt[0])
            self.assertIn("កម្ពុជាជំរុញការវិនិយោគឌីជីថល", received_prompt[0])

        asyncio.run(run_test())

    # ── RED 4: safe_edit handles message splitting & formatting fallback ─
    def test_red_4_safe_edit_long_message_and_fallback(self):
        async def run_test():
            # Test split_message cleanly breaks long texts
            long_text = "ក" * 9000
            chunks = split_message(long_text, max_length=4000)
            self.assertEqual(len(chunks), 3)
            for c in chunks:
                self.assertLessEqual(len(c), 4000)

            # Test safe_edit with long text sends subsequent chunks
            target_msg = MagicMock()
            target_msg.edit_text = AsyncMock()
            target_msg.reply_text = AsyncMock()

            await safe_edit(target_msg, long_text)
            target_msg.edit_text.assert_called_once()
            self.assertEqual(target_msg.reply_text.call_count, 2)

            # Test safe_edit fallback on markdown error
            target_msg.reset_mock()
            target_msg.edit_text = AsyncMock(side_effect=[Exception("Can't parse markdown"), None])
            await safe_edit(target_msg, "Sample *unclosed markdown")
            self.assertEqual(target_msg.edit_text.call_count, 2)

        asyncio.run(run_test())

    # ── ORANGE 5: Daily Ideas Cache and Concurrency Lock ────────────────
    def test_orange_5_ideas_daily_cache_and_lock(self):
        async def run_test():
            ai_mock = MagicMock()
            ai_mock._is_error_response = MagicMock(return_value=False)
            call_count = [0]
            async def mock_gen(prompt, is_json=False):
                call_count[0] += 1
                return "1. 🔥 **គំនិតទី 1៖** គំនិតទីផ្សារឌីជីថល\n🎯 **Hook៖** តើអ្នកត្រៀមខ្លួនហើយឬនៅ?"

            ai_mock.generate_response = AsyncMock(side_effect=mock_gen)

            # First call generates ideas
            b1, ideas1, ev1, err1 = await get_or_generate_ideas(
                self.user, "ទូទៅ", self.storage, ai_mock, force_ai_only=True
            )
            self.assertIsNotNone(b1)
            self.assertEqual(len(ideas1), 1)
            self.assertEqual(call_count[0], 1)

            # Second call for the same category on the same day reuses cache
            b2, ideas2, ev2, err2 = await get_or_generate_ideas(
                self.other_user, "ទូទៅ", self.storage, ai_mock, force_ai_only=False
            )
            self.assertIsNotNone(b2)
            self.assertEqual(len(ideas2), 1)
            self.assertEqual(ideas2[0].topic, ideas1[0].topic)
            # Gemini was NOT called a second time!
            self.assertEqual(call_count[0], 1)

        asyncio.run(run_test())

    # ── ORANGE 6: Refinement Failure passes valid request_id ────────────
    def test_orange_6_refine_retry_uses_request_id(self):
        async def run_test():
            # Setup script version 1
            plan = ScriptPlan(
                title="Test Script",
                target_audience="General",
                hook="Test Hook",
                caption="Caption",
                hashtags=["#test"],
                cta="Follow",
                target_duration_seconds=60,
                estimated_speaking_seconds=55.0,
                is_timeline_valid=True,
                validation_notes="Valid",
                scenes=[Scene(scene_number=1, start_seconds=0, end_seconds=60, spoken_text_km="សួស្តី")],
            )
            req = GenerationRequest(
                id="req_orig_1",
                operation="create",
                owner=self.user,
                draft_snapshot={"topic": "Test", "duration_seconds": 60},
                pace_units_per_second=10.0,
            )
            script = SavedScript(
                id="script_target",
                version=1,
                owner=self.user,
                request_snapshot=req,
                plan=plan,
                created_at=datetime.now(timezone.utc),
            )
            self.storage.save_successful_script(script)

            # Simulate failure during shorten
            ai_mock = MagicMock()
            ai_mock._is_error_response = MagicMock(return_value=True)
            ai_mock.generate_response = AsyncMock(return_value="⚠️ Resource exhausted quota limit")

            token = await self.task_mgr.start_request(self.user, "shorten_req")
            res = await shorten_script(self.user, "script_target", 1, self.storage, ai_mock, self.task_mgr, token)

            self.assertFalse(res.success)
            self.assertIsNotNone(res.request_id)
            self.assertTrue(res.request_id.startswith("req_"))
            self.assertNotEqual(res.request_id, "script_target")

            # Check that storage can retrieve this failed request for retry!
            retrieved_req = self.storage.get_generation_request(res.request_id)
            self.assertIsNotNone(retrieved_req)
            self.assertEqual(retrieved_req.operation, "shorten")

        asyncio.run(run_test())

    # ── ORANGE 7: Hook generation uses TaskManager lock ─────────────────
    def test_orange_7_hook_generation_uses_task_manager(self):
        async def run_test():
            # Setup script
            plan = ScriptPlan(
                title="Test Script",
                target_audience="General",
                hook="Test Hook",
                caption="Caption",
                hashtags=["#test"],
                cta="Follow",
                target_duration_seconds=60,
                estimated_speaking_seconds=55.0,
                is_timeline_valid=True,
                validation_notes="Valid",
                scenes=[Scene(scene_number=1, start_seconds=0, end_seconds=60, spoken_text_km="សួស្តី")],
            )
            req = GenerationRequest(
                id="req_hook_1",
                operation="create",
                owner=self.user,
                draft_snapshot={"topic": "Test", "duration_seconds": 60},
                pace_units_per_second=10.0,
            )
            script = SavedScript(
                id="s_hook_test",
                version=1,
                owner=self.user,
                request_snapshot=req,
                plan=plan,
                created_at=datetime.now(timezone.utc),
            )
            self.storage.save_successful_script(script)

            # User already has a request running
            active_token = await self.task_mgr.start_request(self.user, "another_task")

            ai_mock = MagicMock()
            ai_mock.generate_response = AsyncMock()
            ctx = self._make_mock_context(ai_mock)

            # Trigger hooks action
            upd, q = self._make_mock_update("s:s_hook_test:1:hooks", self.user)
            await handle_script_action_callback(upd, ctx)

            # Must show alert that request is already running, NO AI call made
            q.answer.assert_called_with("⏳ Bot កំពុងដំណើរការសំណើមុន... សូមរង់ចាំមួយភ្លែត!", show_alert=True)
            ai_mock.generate_response.assert_not_called()

        asyncio.run(run_test())

    # ── ORANGE 8: Draft callbacks verify draft.owner ─────────────────────
    def test_orange_8_draft_ownership_enforcement(self):
        async def run_test():
            # Create draft owned by self.user
            draft = Draft(
                id="d_owner_test",
                revision=1,
                format_id="3whs",
                topic="ម្ចាស់ដើម",
                duration_seconds=60,
                audience="ទូទៅ",
                owner=self.user,
            )
            self.storage.save_draft(self.user, draft)

            ctx = self._make_mock_context()

            # 1. other_user tries handle_format_callback
            upd1, q1 = self._make_mock_update(f"f:pov:{draft.id}:1", self.other_user)
            await handle_format_callback(upd1, ctx)
            q1.answer.assert_called_with("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)

            # 2. other_user tries handle_draft_duration_callback
            upd2, q2 = self._make_mock_update(f"d:{draft.id}:1:120", self.other_user)
            await handle_draft_duration_callback(upd2, ctx)
            q2.answer.assert_called_with("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)

            # 3. other_user tries handle_generate_callback
            upd3, q3 = self._make_mock_update(f"g:{draft.id}:1", self.other_user)
            await handle_generate_callback(upd3, ctx)
            q3.answer.assert_called_with("⚠️ អ្នកគ្មានសិទ្ធិបង្កើត Script ពី Draft របស់អ្នកដទៃឡើយ!", show_alert=True)

            # 4. other_user tries handle_comedy_callback
            upd4, q4 = self._make_mock_update(f"c:sty:{draft.id}:1:everyday", self.other_user)
            await handle_comedy_callback(upd4, ctx)
            q4.answer.assert_called_with("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)

            # 5. other_user tries edit_top via menu
            upd5, q5 = self._make_mock_update(f"m:edit_top:{draft.id}", self.other_user)
            await handle_menu_callback(upd5, ctx)
            q5.answer.assert_called_with("⚠️ អ្នកគ្មានសិទ្ធិកែប្រែ Draft របស់អ្នកដទៃឡើយ!", show_alert=True)

            # Verify draft was NOT modified
            unmodified_draft = self.storage.get_draft(draft.id)
            self.assertEqual(unmodified_draft.format_id, "3whs")
            self.assertEqual(unmodified_draft.duration_seconds, 60)
            self.assertEqual(unmodified_draft.revision, 1)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
