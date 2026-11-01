"""
tests/test_draft_recovery.py - Unit and Integration Tests for Draft Recovery from Review Messages.

Verifies that:
1. Multiline topics with dollar signs ($), prices, and Khmer text are recovered with 100% fidelity.
2. Formats, duration, niche, comedy style, and actor counts are accurately restored.
3. If SQLite has no draft (e.g. after Render restart/deploy), handle_generate_callback
   auto-recovers the draft from query.message.text and proceeds to generate smoothly.
"""

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import UserKey, Draft
from app.views import render_review, recover_draft_from_review_text
from app.storage import Storage
from app.navigation import navigation
from app.handlers.creation import handle_generate_callback
from app.callbacks import encode_generate

class TestDraftRecovery(unittest.TestCase):
    def setUp(self):
        self.user_key = UserKey(chat_id=12345, user_id=67890)

    def test_recover_multiline_topic_with_dollar_signs(self):
        topic_text = (
            "1 មុខ 90$ នំប៉័ងសាច់ បាយសិស្សសាលា ស៊ុបគុយទាវ ស៊ុបហ្វឺ មីឆាគីឡូ ។ល។ ជាមីនុយប្រភេទអាហារសម្រន់ពិសេសក្នុងហាង\n\n"
            "2 មុខ 150$ បាយសិស្សសាលា នំប៉័ងសាច់\n"
            "4 មុខ 210$ លតឆា គុយទាវទឹកខៅ នំគួឆាយ\n"
            "ដែលនៅក្នុងនោះគឺថាមីនុយពិសេសនៅប្រចាំហាង\n"
            "ប៉ុន្តែយើងនៅមានពាក់ជាច្រើនទៀត ទាក់ទងជាមួយនឹងអាហារសម្រន់"
        )
        draft = Draft(
            id="d_testfood",
            revision=1,
            format_id="3whs",
            topic=topic_text,
            duration_seconds=60,
            audience=topic_text,
            current_step="review",
            owner=self.user_key,
            niche="សាលាបង្រៀនធ្វើម្ហូបអនឡាញ",
        )
        rendered = render_review(draft, 10.0)

        recovered = recover_draft_from_review_text(rendered, self.user_key, draft_id="d_testfood")
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.id, "d_testfood")
        self.assertEqual(recovered.format_id, "3whs")
        self.assertEqual(recovered.duration_seconds, 60)
        self.assertEqual(recovered.niche, "សាលាបង្រៀនធ្វើម្ហូបអនឡាញ")
        self.assertEqual(recovered.topic, topic_text)
        self.assertEqual(recovered.owner, self.user_key)

    def test_recover_from_telegram_plain_text(self):
        """Telegram strips markdown formatting like * and ` in query.message.text."""
        plain_text = (
            "📋 ផ្ទៀងផ្ទាត់ព័ត៌មានសំណើ (Draft Review)\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "• 🎯 វិស័យមាតិកា: សាលាបង្រៀនធ្វើម្ហូបអនឡាញ\n"
            "• 🎬 ទម្រង់មាតិកា: 🎬 ស្គ្រីប 3WHs Hook\n"
            "• 📝 ប្រធានបទ: 1 មុខ 90$ នំប៉័ងសាច់ បាយសិស្សសាលា\n\n"
            "2 មុខ 150$ បាយសិស្សសាលា នំប៉័ងសាច់\n"
            "4 មុខ 210$ លតឆា គុយទាវទឹកខៅ\n"
            "• ⏱️ រយៈពេលវីដេអូ: 1 នាទី (60 វិនាទី)\n"
            "• 🎙️ ល្បឿននិយាយប៉ាន់ស្មាន: 10.0 តួអក្សរ/វិនាទី\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 ពិនិត្យព័ត៌មានខាងលើ រួចចុច «✨ បង្កើត Script» ដើម្បីឱ្យ AI រៀបចំផែនការថត!"
        )
        recovered = recover_draft_from_review_text(plain_text, self.user_key, draft_id="d_from_plain")
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.id, "d_from_plain")
        self.assertEqual(recovered.format_id, "3whs")
        self.assertEqual(recovered.duration_seconds, 60)
        self.assertEqual(recovered.niche, "សាលាបង្រៀនធ្វើម្ហូបអនឡាញ")
        self.assertIn("1 មុខ 90$", recovered.topic)
        self.assertIn("4 មុខ 210$", recovered.topic)

    def test_recover_comedy_format_with_style_and_actors(self):
        draft = Draft(
            id="d_comedy123",
            revision=1,
            format_id="comedy",
            topic="មិត្តភក្តិខ្ចីលុយមិនសង",
            duration_seconds=30,
            audience="មិត្តភក្តិខ្ចីលុយមិនសង",
            comedy_style="everyday",
            actor_count=2,
            current_step="review",
            owner=self.user_key,
            niche="ការកម្សាន្ត",
        )
        rendered = render_review(draft, 10.0)

        recovered = recover_draft_from_review_text(rendered, self.user_key, draft_id="d_comedy123")
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.format_id, "comedy")
        self.assertEqual(recovered.duration_seconds, 30)
        self.assertEqual(recovered.comedy_style, "everyday")
        self.assertEqual(recovered.actor_count, 2)
        self.assertEqual(recovered.topic, "មិត្តភក្តិខ្ចីលុយមិនសង")

    def test_recover_different_durations(self):
        durations = [30, 60, 120, 180, 300]
        for dur in durations:
            draft = Draft(
                id=f"d_dur_{dur}",
                revision=1,
                format_id="pov",
                topic=f"ប្រធានបទសាកល្បង {dur} វិនាទី",
                duration_seconds=dur,
                audience="test",
                current_step="review",
                owner=self.user_key,
                niche="បច្ចេកវិទ្យា",
            )
            rendered = render_review(draft, 10.0)
            recovered = recover_draft_from_review_text(rendered, self.user_key, draft_id=draft.id)
            self.assertIsNotNone(recovered)
            self.assertEqual(recovered.duration_seconds, dur)
            self.assertEqual(recovered.format_id, "pov")

    def test_recover_returns_none_for_invalid_text(self):
        self.assertIsNone(recover_draft_from_review_text("", self.user_key))
        self.assertIsNone(recover_draft_from_review_text("ជំរាបសួរ អរគុណ", self.user_key))

class TestGenerateCallbackRecoveryIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_recovery.sqlite3")
        self.storage = Storage(db_path=self.db_path)
        navigation.set_storage(self.storage)
        self.user_key = UserKey(chat_id=12345, user_id=67890)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_handle_generate_recovers_draft_when_storage_is_empty(self):
        """Simulates clicking [✨ បង្កើត Script] right after Render redeploy/restart with empty SQLite."""
        # Ensure database is completely empty
        self.assertIsNone(self.storage.get_draft("d_ephemeral"))
        self.assertIsNone(self.storage.get_latest_draft(self.user_key))

        # Review message text as seen by user in Telegram
        review_msg_text = (
            "📋 ផ្ទៀងផ្ទាត់ព័ត៌មានសំណើ (Draft Review)\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "• 🎯 វិស័យមាតិកា: សាលាបង្រៀនធ្វើម្ហូបអនឡាញ\n"
            "• 🎬 ទម្រង់មាតិកា: 🎬 ស្គ្រីប 3WHs Hook\n"
            "• 📝 ប្រធានបទ: 1 មុខ 90$ នំប៉័ងសាច់ បាយសិស្សសាលា\n"
            "2 មុខ 150$ បាយសិស្សសាលា\n"
            "• ⏱️ រយៈពេលវីដេអូ: 1 នាទី (60 វិនាទី)\n"
            "• 🎙️ ល្បឿននិយាយប៉ាន់ស្មាន: 10.0 តួអក្សរ/វិនាទី\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 ពិនិត្យព័ត៌មានខាងលើ រួចចុច «✨ បង្កើត Script» ដើម្បីឱ្យ AI រៀបចំផែនការថត!"
        )

        update = MagicMock()
        query = MagicMock()
        query.data = encode_generate("d_ephemeral", 1)
        query.answer = AsyncMock()
        query.message = MagicMock()
        query.message.text = review_msg_text
        query.message.reply_text = AsyncMock()
        update.callback_query = query
        update.effective_chat.id = self.user_key.chat_id
        update.effective_user.id = self.user_key.user_id

        mock_task_mgr = MagicMock()
        mock_task_mgr.start_request = AsyncMock(return_value=1)
        mock_task_mgr.is_current_request = MagicMock(return_value=True)
        mock_task_mgr.finish_request = AsyncMock()

        mock_ai = MagicMock()

        context = MagicMock()
        context.bot_data = {
            "storage": self.storage,
            "task_mgr": mock_task_mgr,
            "ai": mock_ai,
        }

        with patch("app.handlers.creation.execute_generation_request") as mock_exec:
            mock_plan = MagicMock()
            mock_plan.target_duration_seconds = 60
            mock_plan.estimated_speaking_seconds = 55.0
            mock_plan.scenes = []
            mock_plan.estimated_pace_units_per_second = 10.0
            mock_plan.total_dialogue_units = 500

            mock_script = MagicMock()
            mock_script.id = "s_test"
            mock_script.version = 1
            mock_script.plan = mock_plan

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.script = mock_script
            mock_exec.return_value = mock_result

            with patch("app.handlers.creation.safe_edit", new_callable=AsyncMock):
                await handle_generate_callback(update, context)

        # Verified: Did NOT show the "Please enter topic first" alert
        query.answer.assert_any_call("✨ កំពុងចាប់ផ្តើមបង្កើត Script...")

        # Verified: Draft was automatically restored and persisted in SQLite
        saved_draft = self.storage.get_draft("d_ephemeral")
        self.assertIsNotNone(saved_draft)
        self.assertEqual(saved_draft.format_id, "3whs")
        self.assertEqual(saved_draft.niche, "សាលាបង្រៀនធ្វើម្ហូបអនឡាញ")
        self.assertIn("1 មុខ 90$", saved_draft.topic)

if __name__ == "__main__":
    unittest.main()
