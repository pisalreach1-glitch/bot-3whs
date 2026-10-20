"""
tests/test_comedy_and_script_flows.py - Unit tests verifying complete comedy flow,
niche intent preservation, safe Markdown generation, and back navigation.
"""

import json
import tempfile
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import UserKey, Draft, GenerationRequest
from app.storage import Storage
from app.task_manager import TaskManager
from app.navigation import navigation, Screens
from app.handlers.menu import handle_menu_callback, render_current_screen
from app.handlers.creation import handle_format_callback, handle_generate_callback
from app.handlers.comedy import handle_comedy_callback
from bot import handle_text_message


class TestComedyAndScriptFlows(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_flow.sqlite3"
        self.storage = Storage(db_path=self.db_path)
        self.task_mgr = TaskManager()
        self.user = UserKey(chat_id=101, user_id=202)
        navigation.clear()

    def tearDown(self):
        navigation.clear()
        self.temp_dir.cleanup()

    def test_comedy_flow_with_saved_niche(self):
        async def run_test():
            self.storage.save_user_niche(self.user, "🍜 ម្ហូបអាហារ / ចម្អិន")

            # 1. Click 😂 បង្កើតកំប្លែង (m:comedy)
            update = MagicMock()
            update.effective_chat.id = self.user.chat_id
            update.effective_user.id = self.user.user_id
            update.callback_query.data = "m:comedy"
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            update.callback_query.message = MagicMock()

            context = MagicMock()
            context.bot_data = {
                "storage": self.storage,
                "task_mgr": self.task_mgr,
            }
            context.user_data = {}

            await handle_menu_callback(update, context)

            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.COMEDY_STYLE)
            self.assertIsNotNone(state.draft_id)

            draft = self.storage.get_draft(state.draft_id)
            self.assertIsNotNone(draft)
            self.assertEqual(draft.format_id, "comedy")
            self.assertEqual(draft.niche, "🍜 ម្ហូបអាហារ / ចម្អិន")

            # Verify edit called with comedy styles keyboard
            self.assertTrue(update.callback_query.edit_message_text.called)
            args = update.callback_query.edit_message_text.call_args[0]
            self.assertIn("ជ្រើសរើសស្ទីលកំប្លែង", args[0])

            # 2. Select Style: c:sty:<draft_id>:<rev>:parody
            style_update = MagicMock()
            style_update.effective_chat.id = self.user.chat_id
            style_update.effective_user.id = self.user.user_id
            style_update.callback_query.data = f"c:sty:{draft.id}:{draft.revision}:parody"
            style_update.callback_query.answer = AsyncMock()
            style_update.callback_query.edit_message_text = AsyncMock()
            style_update.callback_query.message = MagicMock()

            await handle_comedy_callback(style_update, context)

            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.COMEDY_ACTORS)
            draft = self.storage.get_draft(draft.id)
            self.assertEqual(draft.comedy_style, "parody")

            # 3. Select Actors: c:act:<draft_id>:<rev>:2
            actor_update = MagicMock()
            actor_update.effective_chat.id = self.user.chat_id
            actor_update.effective_user.id = self.user.user_id
            actor_update.callback_query.data = f"c:act:{draft.id}:{draft.revision}:2"
            actor_update.callback_query.answer = AsyncMock()
            actor_update.callback_query.edit_message_text = AsyncMock()
            actor_update.callback_query.message = MagicMock()

            await handle_comedy_callback(actor_update, context)

            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.TOPIC_INPUT)
            draft = self.storage.get_draft(draft.id)
            self.assertEqual(draft.actor_count, 2)

            # 4. User types topic in chat
            text_update = MagicMock()
            text_update.effective_chat.id = self.user.chat_id
            text_update.effective_user.id = self.user.user_id
            text_update.message.text = "ពេលសុំច្បាប់មេ តែជួបមេនៅផ្សារ"
            text_update.message.reply_text = AsyncMock()

            await handle_text_message(text_update, context)

            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.DRAFT_REVIEW)
            draft = self.storage.get_draft(draft.id)
            self.assertEqual(draft.topic, "ពេលសុំច្បាប់មេ តែជួបមេនៅផ្សារ")
            self.assertTrue(text_update.message.reply_text.called)

        asyncio.run(run_test())

    def test_comedy_flow_first_visit_prompts_niche_then_goes_to_comedy(self):
        async def run_test():
            # User has NO niche set
            update = MagicMock()
            update.effective_chat.id = self.user.chat_id
            update.effective_user.id = self.user.user_id
            update.callback_query.data = "m:comedy"
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            update.callback_query.message = MagicMock()

            context = MagicMock()
            context.bot_data = {
                "storage": self.storage,
                "task_mgr": self.task_mgr,
            }
            context.user_data = {}

            await handle_menu_callback(update, context)

            # Should navigate to NICHE_SELECTION and set pending_action == "comedy"
            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.NICHE_SELECTION)
            self.assertEqual(context.user_data.get("pending_action"), "comedy")

            # Now user picks a niche: m:niche:food
            niche_update = MagicMock()
            niche_update.effective_chat.id = self.user.chat_id
            niche_update.effective_user.id = self.user.user_id
            niche_update.callback_query.data = "m:niche:food"
            niche_update.callback_query.answer = AsyncMock()
            niche_update.callback_query.edit_message_text = AsyncMock()
            niche_update.callback_query.message = MagicMock()

            await handle_menu_callback(niche_update, context)

            # Should now be on COMEDY_STYLE!
            state = navigation.get_state(self.user)
            self.assertEqual(state.current_screen, Screens.COMEDY_STYLE)
            draft = self.storage.get_draft(state.draft_id)
            self.assertEqual(draft.format_id, "comedy")

        asyncio.run(run_test())

    def test_safe_generation_with_special_markdown_chars_in_topic(self):
        async def run_test():
            self.storage.save_user_niche(self.user, "Tech")
            draft = Draft(
                id="d_special_topic",
                revision=2,
                format_id="3whs",
                topic="How to use [AI] tools _properly_ *2026*",
                duration_seconds=60,
                audience="All",
                owner=self.user,
                niche="Tech",
            )
            self.storage.save_draft(self.user, draft)

            update = MagicMock()
            update.effective_chat.id = self.user.chat_id
            update.effective_user.id = self.user.user_id
            update.callback_query.data = f"g:{draft.id}:{draft.revision}"
            update.callback_query.answer = AsyncMock()

            status_msg_mock = MagicMock()
            status_msg_mock.edit_text = AsyncMock()
            status_msg_mock.reply_text = AsyncMock()

            # Simulate reply_text succeeding
            update.callback_query.message.reply_text = AsyncMock(return_value=status_msg_mock)

            ai_mock = MagicMock()
            valid_json = json.dumps({
                "title": "AI Tools Script",
                "target_audience": "Tech enthusiasts",
                "hook": "Hook",
                "caption": "Caption",
                "hashtags": ["#AI"],
                "cta": "Follow for more",
                "scenes": [
                    {
                        "scene_number": 1,
                        "start_seconds": 0,
                        "end_seconds": 60,
                        "spoken_text_km": "ការប្រើប្រាស់ AI ឱ្យបានត្រឹមត្រូវ",
                        "shot_size": "Medium Shot",
                        "camera_action": "Static",
                        "visual_action": "Demo on laptop",
                        "on_screen_text_km": "AI Tips",
                        "editing_note": "Direct cut",
                        "audio_note": "Natural audio",
                    }
                ]
            })
            ai_mock.generate_response = AsyncMock(return_value=valid_json)
            ai_mock._is_error_response = MagicMock(return_value=False)

            context = MagicMock()
            context.bot_data = {
                "storage": self.storage,
                "task_mgr": self.task_mgr,
                "ai": ai_mock,
            }

            await handle_generate_callback(update, context)

            # Verify generation completed without unhandled exception and task lock is released
            self.assertIsNone(self.task_mgr.get_active_request(self.user))
            last_script = self.storage.get_last_successful_script(self.user)
            self.assertIsNotNone(last_script)
            self.assertEqual(last_script.plan.title, "AI Tools Script")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
