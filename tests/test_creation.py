"""
tests/test_creation.py - Tests for Format selection, Topic review, Generation pipeline, Durations, and Retry.
"""

import json
import tempfile
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import (
    UserKey,
    Draft,
    GenerationRequest,
    SavedScript,
    GenerationResult,
    ErrorCodes,
)
from app.storage import Storage
from app.task_manager import TaskManager
from app.services.generation import execute_generation_request

class TestCreationFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_creation.sqlite3"
        self.storage = Storage(db_path=self.db_path)
        self.task_mgr = TaskManager()
        self.user = UserKey(chat_id=101, user_id=202)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_valid_plan_json(self, duration_s: int):
        return json.dumps({
            "title": "Script Title",
            "target_audience": "Audience",
            "hook": "Strong Hook",
            "caption": "Video Caption",
            "hashtags": ["#khmer", "#video"],
            "cta": "Like and share",
            "scenes": [
                {
                    "scene_number": 1,
                    "start_seconds": 0,
                    "end_seconds": duration_s,
                    "spoken_text_km": "សួស្តីបងប្អូនទាំងអស់គ្នា",
                    "shot_size": "Medium Shot",
                    "camera_action": "Static",
                    "visual_action": "Host speaking clearly",
                    "on_screen_text_km": "3WHs Video",
                    "editing_note": "Cut directly",
                    "audio_note": "Soft music",
                }
            ]
        })

    async def _async_test_all_six_formats_and_comedy(self):
        formats = ["3whs", "pov", "myth", "transform", "hottake", "toplist", "comedy"]
        ai_mock = MagicMock()

        for fmt in formats:
            draft = Draft(
                id=f"draft_{fmt}",
                revision=1,
                format_id=fmt,
                topic=f"Testing {fmt}",
                duration_seconds=60,
                audience="General Audience",
                comedy_style="everyday" if fmt == "comedy" else None,
                actor_count=2 if fmt == "comedy" else None,
            )
            req = GenerationRequest(
                id=f"req_{fmt}",
                operation="create",
                owner=self.user,
                draft_snapshot=draft.to_snapshot(),
                pace_units_per_second=10.0,
            )

            ai_mock.generate_response = AsyncMock(return_value=self._make_valid_plan_json(60))
            ai_mock._is_error_response = MagicMock(return_value=False)

            token = await self.task_mgr.start_request(self.user, req.id)
            result = await execute_generation_request(req, self.storage, ai_mock, token, self.task_mgr)
            await self.task_mgr.finish_request(self.user, token)

            self.assertTrue(result.success, f"Format {fmt} failed generation: {result.user_message_km}")
            self.assertIsNotNone(result.script)
            self.assertEqual(result.script.plan.target_duration_seconds, 60)

    def test_all_six_formats_and_comedy(self):
        asyncio.run(self._async_test_all_six_formats_and_comedy())

    async def _async_test_all_four_durations(self):
        ai_mock = MagicMock()
        ai_mock._is_error_response = MagicMock(return_value=False)

        for duration in [60, 120, 180, 300]:
            draft = Draft(
                id=f"draft_dur_{duration}",
                revision=1,
                format_id="3whs",
                topic=f"Topic for {duration}s",
                duration_seconds=duration,
                audience="General",
            )
            req = GenerationRequest(
                id=f"req_dur_{duration}",
                operation="create",
                owner=self.user,
                draft_snapshot=draft.to_snapshot(),
                pace_units_per_second=10.0,
            )

            ai_mock.generate_response = AsyncMock(return_value=self._make_valid_plan_json(duration))
            token = await self.task_mgr.start_request(self.user, req.id)
            result = await execute_generation_request(req, self.storage, ai_mock, token, self.task_mgr)
            await self.task_mgr.finish_request(self.user, token)

            self.assertTrue(result.success)
            self.assertEqual(result.script.plan.target_duration_seconds, duration)

    def test_all_four_durations(self):
        asyncio.run(self._async_test_all_four_durations())

    async def _async_test_invalid_json_preserves_last_script(self):
        # 1. Establish existing successful script
        ai_mock = MagicMock()
        ai_mock._is_error_response = MagicMock(return_value=False)
        ai_mock.generate_response = AsyncMock(return_value=self._make_valid_plan_json(60))

        draft_ok = Draft(id="d_ok", revision=1, format_id="3whs", topic="Good Topic", duration_seconds=60, audience="All")
        req_ok = GenerationRequest(id="req_ok", operation="create", owner=self.user, draft_snapshot=draft_ok.to_snapshot(), pace_units_per_second=10.0)

        tok_ok = await self.task_mgr.start_request(self.user, req_ok.id)
        res_ok = await execute_generation_request(req_ok, self.storage, ai_mock, tok_ok, self.task_mgr)
        await self.task_mgr.finish_request(self.user, tok_ok)
        self.assertTrue(res_ok.success)

        # 2. Run invalid JSON response
        ai_mock.generate_response = AsyncMock(return_value="NOT A VALID JSON OBJECT {{{")
        draft_bad = Draft(id="d_bad", revision=1, format_id="3whs", topic="Bad JSON Topic", duration_seconds=60, audience="All")
        req_bad = GenerationRequest(id="req_bad", operation="create", owner=self.user, draft_snapshot=draft_bad.to_snapshot(), pace_units_per_second=10.0)

        tok_bad = await self.task_mgr.start_request(self.user, req_bad.id)
        res_bad = await execute_generation_request(req_bad, self.storage, ai_mock, tok_bad, self.task_mgr)
        await self.task_mgr.finish_request(self.user, tok_bad)

        self.assertFalse(res_bad.success)
        self.assertEqual(res_bad.error_code, ErrorCodes.INVALID_SCHEMA)

        # 3. Last successful script MUST REMAIN the previous one
        last_script = self.storage.get_last_successful_script(self.user)
        self.assertIsNotNone(last_script)
        self.assertEqual(last_script.id, "req_ok")

        # 4. Failed request saved for retry
        failed_entry = self.storage.get_last_failed_request(self.user)
        self.assertIsNotNone(failed_entry)
        req, err, msg = failed_entry
        self.assertEqual(req.id, "req_bad")
        self.assertEqual(req.draft_snapshot["topic"], "Bad JSON Topic")

    def test_invalid_json_preserves_last_script(self):
        asyncio.run(self._async_test_invalid_json_preserves_last_script())

    async def _async_test_cancelled_request_never_saves(self):
        ai_mock = MagicMock()
        ai_mock._is_error_response = MagicMock(return_value=False)
        ai_mock.generate_response = AsyncMock(return_value=self._make_valid_plan_json(60))

        draft = Draft(id="d_cancel", revision=1, format_id="3whs", topic="Cancel Me", duration_seconds=60, audience="All")
        req = GenerationRequest(id="req_cancel", operation="create", owner=self.user, draft_snapshot=draft.to_snapshot(), pace_units_per_second=10.0)

        token = await self.task_mgr.start_request(self.user, req.id)
        # User cancels during processing
        await self.task_mgr.cancel_request(self.user)

        res = await execute_generation_request(req, self.storage, ai_mock, token, self.task_mgr)
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, ErrorCodes.CANCELLED)

        # Script must NOT be saved
        script = self.storage.get_script("req_cancel", 1)
        self.assertIsNone(script)

    def test_cancelled_request_never_saves(self):
        asyncio.run(self._async_test_cancelled_request_never_saves())

    def test_multiline_topic_with_dollar_signs_handles_cleanly(self):
        """User input containing newlines and dollar signs creates valid draft and render review."""
        from bot import handle_text_message
        from app.navigation import navigation, Screens
        from telegram import Update, Message, User, Chat

        user_text = """1 មុខ 90$ នំប៉័ងសាច់ បាយសិស្សសាលា ស៊ុបគុយទាវ ស៊ុបហ្វឺ មីឆាគីឡូ ។ល។ ជាមីនុយប្រភេទអាហារសម្រន់ពិសេសក្នុងហាង

2 មុខ 150$ បាយសិស្សសាលា នំប៉័ងសាច់
4 មុខ 210$ លតឆា គុយទាវទឹកក្ដៅ នំគួឆាយ
ដែលនៅក្នុងនោះគឺថាមីនុយពិសេសនៅប្រចាំហាង
ប៉ុន្តែយើងនៅមានពាក់ជាច្រើនទៀត ទាក់ទងជាមួយនឹងអាហារសម្រន់"""

        # Setup draft in storage and navigation
        draft = Draft(
            id="d_food_test",
            revision=1,
            format_id="3whs",
            topic="",
            duration_seconds=60,
            audience="",
            current_step="topic",
            owner=self.user,
            niche="សាលាបង្រៀនធ្វើម្ហូបអនឡាញ",
        )
        self.storage.save_draft(self.user, draft)
        navigation.set_storage(self.storage)
        navigation.go_to(self.user, Screens.TOPIC_INPUT, draft_id="d_food_test")

        # Mock telegram update
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.text = user_text
        message.from_user = User(id=self.user.user_id, is_bot=False, first_name="TestUser")
        message.chat = Chat(id=self.user.chat_id, type="private")
        message.reply_text = AsyncMock()
        update.message = message
        update.effective_user = message.from_user
        update.effective_chat = message.chat

        context = MagicMock()
        context.bot_data = {
            "storage": self.storage,
            "ai": MagicMock(),
            "task_mgr": self.task_mgr,
        }

        asyncio.run(handle_text_message(update, context))

        # Check that draft updated with user's topic
        updated_draft = self.storage.get_draft("d_food_test")
        self.assertIsNotNone(updated_draft)
        self.assertEqual(updated_draft.topic, user_text)
        self.assertEqual(updated_draft.current_step, "review")

        # Check message was replied to with review
        message.reply_text.assert_called()
        call_text = message.reply_text.call_args[0][0]
        self.assertIn("ផ្ទៀងផ្ទាត់ព័ត៌មានសំណើ", call_text)
        self.assertIn("1 មុខ 90$", call_text)

if __name__ == "__main__":
    unittest.main()
