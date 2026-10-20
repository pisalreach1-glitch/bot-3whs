"""
tests/test_niche_and_formats.py - Comprehensive tests for:
- All 6 original formats + Comedy as 7th choice
- Persistent user niche storage, reuse, and changing without erasing successful scripts
- Separation of niche and format/topic
- Ideas matching niche and format with honest evidence labeling
- Preserving selected format when choosing ideas
- Retry and regeneration preserving exact snapshots
- Cache isolation between niches and formats
- Back navigation state preservation
"""

import json
import uuid
import tempfile
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.models import (
    UserKey,
    Draft,
    GenerationRequest,
    SavedScript,
    Idea,
    EvidenceRecord,
)
from app.storage import Storage
from app.task_manager import TaskManager
from app.navigation import navigation, Screens
from app.keyboards import (
    FORMAT_DEFINITIONS,
    NICHE_DEFINITIONS,
    get_format_selection_keyboard,
    get_niche_selection_keyboard,
    get_topic_or_ideas_keyboard,
)
from app.views import FORMAT_NAMES, render_format_selection, render_topic_or_ideas, render_review
from app.services.generation import execute_generation_request
from app.services.ideas import get_or_generate_ideas, _DAILY_IDEAS_CACHE
from app.services.refinements import regenerate_script
from app.handlers.ideas import handle_idea_pick_callback
from app.callbacks import encode_idea_pick
from script_models import ScriptPlan, Scene

class TestNicheAndFormats(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_niche.sqlite3"
        self.storage = Storage(db_path=self.db_path)
        self.task_mgr = TaskManager()
        self.user = UserKey(chat_id=101, user_id=202)
        _DAILY_IDEAS_CACHE.clear()

    def tearDown(self):
        self.temp_dir.cleanup()
        _DAILY_IDEAS_CACHE.clear()

    def _make_valid_plan_json(self, duration_s: int = 60):
        return json.dumps({
            "title": "Niche Test Script",
            "target_audience": "Specific Audience",
            "hook": "Compelling Hook",
            "caption": "Social Caption",
            "hashtags": ["#test", "#niche"],
            "cta": "Follow for more",
            "scenes": [
                {
                    "scene_number": 1,
                    "start_seconds": 0,
                    "end_seconds": duration_s,
                    "spoken_text_km": "សួស្តីអ្នកទាំងអស់គ្នា នេះជាវីដេអូសាកល្បង",
                    "shot_size": "Medium Shot",
                    "camera_action": "Static",
                    "visual_action": "Host speaking",
                    "on_screen_text_km": "Topic Title",
                    "editing_note": "Cut directly",
                    "audio_note": "Soft music",
                }
            ]
        })

    # 1. All original six formats + Comedy as 7th choice
    def test_all_seven_formats_visible_and_available(self):
        format_ids = [fid for fid, label in FORMAT_DEFINITIONS]
        self.assertEqual(len(format_ids), 7)
        self.assertIn("3whs", format_ids)
        self.assertIn("pov", format_ids)
        self.assertIn("myth", format_ids)
        self.assertIn("transform", format_ids)
        self.assertIn("hottake", format_ids)
        self.assertIn("toplist", format_ids)
        self.assertIn("comedy", format_ids)

        draft = Draft(
            id="d_test",
            revision=1,
            format_id="3whs",
            topic="",
            duration_seconds=60,
            audience="",
            current_step="format",
            owner=self.user,
            niche="Food / Cooking",
        )
        kb = get_format_selection_keyboard(draft)
        # Should contain "✏️ ប្ដូរវិស័យ" button plus 7 format buttons plus nav buttons
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in all_buttons]
        self.assertTrue(any("ប្ដូរវិស័យ" in txt for txt in button_texts))
        self.assertTrue(any("3WHs" in txt for txt in button_texts))
        self.assertTrue(any("POV" in txt for txt in button_texts))
        self.assertTrue(any("Myth" in txt or "ជំនឿខុស" in txt for txt in button_texts))
        self.assertTrue(any("Before & After" in txt or "មុន & ក្រោយ" in txt for txt in button_texts))
        self.assertTrue(any("Hot Take" in txt or "មតិផ្ទុយ" in txt for txt in button_texts))
        self.assertTrue(any("Top List" in txt or "បញ្ជីកំពូល" in txt for txt in button_texts))
        self.assertTrue(any("Comedy" in txt or "កំប្លែង" in txt for txt in button_texts))

    # 2. Saved niche is stored and reused
    def test_saved_niche_storage_and_reuse(self):
        # Initial: no niche
        self.assertIsNone(self.storage.get_user_niche(self.user))

        # Save niche
        self.storage.save_user_niche(self.user, "🍜 Food / Cooking")
        self.assertEqual(self.storage.get_user_niche(self.user), "🍜 Food / Cooking")

        # In settings
        settings = self.storage.get_settings(self.user)
        self.assertEqual(settings["niche"], "🍜 Food / Cooking")

        # Update niche
        self.storage.save_user_niche(self.user, "📱 Technology / AI")
        self.assertEqual(self.storage.get_user_niche(self.user), "📱 Technology / AI")

    # 3. Niche and topic remain separate in data models and generation
    def test_niche_and_topic_remain_separate(self):
        draft = Draft(
            id="d_sep",
            revision=1,
            format_id="myth",
            topic="Does delicious cooking always require lots of seasoning?",
            duration_seconds=60,
            audience="Khmer home cooks",
            current_step="review",
            owner=self.user,
            niche="Khmer cooking",
        )
        data = draft.to_dict()
        self.assertEqual(data["niche"], "Khmer cooking")
        self.assertEqual(data["topic"], "Does delicious cooking always require lots of seasoning?")
        self.assertNotEqual(data["niche"], data["topic"])

        restored = Draft.from_dict(data)
        self.assertEqual(restored.niche, "Khmer cooking")
        self.assertEqual(restored.topic, "Does delicious cooking always require lots of seasoning?")

        # Generation preserves niche and topic separately in prompts
        async def run_gen():
            ai_mock = MagicMock()
            ai_mock._is_error_response = MagicMock(return_value=False)
            captured_prompts = []
            async def mock_gen(prompt, is_json=True):
                captured_prompts.append(prompt)
                return self._make_valid_plan_json(60)

            ai_mock.generate_response = AsyncMock(side_effect=mock_gen)

            req = GenerationRequest(
                id="req_sep_1",
                operation="create",
                owner=self.user,
                draft_snapshot=draft.to_dict(),
                pace_units_per_second=10.0,
            )
            token = await self.task_mgr.start_request(self.user, req.id)
            res = await execute_generation_request(req, self.storage, ai_mock, token, self.task_mgr)
            self.assertTrue(res.success)
            self.assertEqual(len(captured_prompts), 1)
            prompt = captured_prompts[0]
            # Prompt must mention niche and topic separately
            self.assertIn("Khmer cooking", prompt)
            self.assertIn("Does delicious cooking always require lots of seasoning?", prompt)

        asyncio.run(run_gen())

    # 4. Ideas match niche and format & unsupported niches use honest AI-only
    def test_ideas_match_niche_and_format(self):
        async def run_ideas():
            ai_mock = MagicMock()
            ai_mock._is_error_response = MagicMock(return_value=False)
            captured_prompts = []
            async def mock_gen(prompt, is_json=False):
                captured_prompts.append(prompt)
                return (
                    "1. 🔥 **គំនិតទី 1៖** កំហុសក្នុងការឆុងកាហ្វេ Espresso\n"
                    "🎯 **Hook៖** តើអ្នកធ្លាប់ឆុងកាហ្វេជូរដែរឬទេ?\n"
                    "📋 **Format៖** Myth vs Reality\n"
                    "2. 🔥 **គំនិតទី 2៖** គ្រាប់កាហ្វេ Robusta vs Arabica\n"
                    "🎯 **Hook៖** កុំទើបតែផឹកកាហ្វេបើមិនទាន់ដឹងរឿងនេះ!\n"
                    "📋 **Format៖** Myth vs Reality\n"
                    "3. 🔥 **គំនិតទី 3៖** ទឹកសម្រាប់ឆុងកាហ្វេ\n"
                    "🎯 **Hook៖** រសជាតិកាហ្វេខូចដោយសារទឹក!\n"
                    "📋 **Format៖** Myth vs Reality\n"
                )

            ai_mock.generate_response = AsyncMock(side_effect=mock_gen)

            # Request ideas for coffee with myth format
            b_token, ideas, ev, err = await get_or_generate_ideas(
                user_key=self.user,
                category="☕️ Coffee / Beverages",
                storage=self.storage,
                ai=ai_mock,
                format_id="myth",
            )
            self.assertIsNone(err)
            self.assertEqual(len(ideas), 3)
            # Coffee is unsupported for news -> honest AI-only mode
            self.assertEqual(len(ev), 0)
            for i in ideas:
                self.assertEqual(i.evidence_status, "ai_only")
            self.assertEqual(len(captured_prompts), 1)
            self.assertIn("Coffee", captured_prompts[0])
            self.assertIn("Myth vs Reality", captured_prompts[0])

        asyncio.run(run_ideas())

    # 5. Selecting an idea preserves the selected format
    def test_selecting_idea_preserves_selected_format(self):
        async def run_pick():
            # Setup draft with format 'myth'
            draft = Draft(
                id="d_pick_fmt",
                revision=1,
                format_id="myth",
                topic="",
                duration_seconds=60,
                audience="",
                current_step="topic_or_ideas",
                owner=self.user,
                niche="☕️ Coffee / Beverages",
            )
            self.storage.save_draft(self.user, draft)
            navigation.go_to(self.user, Screens.IDEA_RESULTS, draft_id=draft.id)

            # Setup batch where AI suggests 'pov'
            ideas = [
                Idea(
                    id=1,
                    topic="The Art of Coffee Brewing",
                    hook="Best coffee ever",
                    suggested_format="pov",
                    source_ids=[],
                    evidence_status="ai_only",
                )
            ]
            batch_token = "b_pick_123"
            self.storage.save_idea_batch(batch_token, self.user, "Coffee", ideas, [])

            # Mock update and callback
            update = MagicMock()
            update.callback_query = MagicMock()
            update.callback_query.data = encode_idea_pick(batch_token, 1)
            update.callback_query.answer = AsyncMock()
            update.callback_query.edit_message_text = AsyncMock()
            update.effective_chat.id = self.user.chat_id
            update.effective_user.id = self.user.user_id

            context = MagicMock()
            context.bot_data = {"storage": self.storage}

            await handle_idea_pick_callback(update, context)

            # Verify draft
            saved_draft = self.storage.get_draft("d_pick_fmt")
            self.assertIsNotNone(saved_draft)
            self.assertEqual(saved_draft.topic, "The Art of Coffee Brewing")
            # CRITICAL: Format must remain 'myth' and NOT overwritten by AI's 'pov'
            self.assertEqual(saved_draft.format_id, "myth")
            self.assertEqual(saved_draft.niche, "☕️ Coffee / Beverages")

        asyncio.run(run_pick())

    # 6. Retry and regeneration preserve the request snapshot
    def test_retry_and_regeneration_preserve_snapshot(self):
        async def run_retry():
            draft_snap = {
                "id": "d_snap_1",
                "format_id": "transform",
                "topic": "Before & After Learning Python",
                "duration_seconds": 60,
                "audience": "New programmers",
                "niche": "📚 Education / Skills",
            }
            req = GenerationRequest(
                id="req_failed_1",
                operation="create",
                owner=self.user,
                draft_snapshot=draft_snap,
                pace_units_per_second=10.0,
            )
            self.storage.save_failed_request(self.user, req, "API_ERROR", "Temporary network failure")

            # Retrieve failed request
            failed_req = self.storage.get_generation_request("req_failed_1")
            self.assertIsNotNone(failed_req)
            self.assertEqual(failed_req.draft_snapshot["niche"], "📚 Education / Skills")
            self.assertEqual(failed_req.draft_snapshot["format_id"], "transform")
            self.assertEqual(failed_req.draft_snapshot["topic"], "Before & After Learning Python")

            # Execute retry
            ai_mock = MagicMock()
            ai_mock._is_error_response = MagicMock(return_value=False)
            captured_prompts = []
            async def mock_gen(prompt, is_json=True):
                captured_prompts.append(prompt)
                return self._make_valid_plan_json(60)

            ai_mock.generate_response = AsyncMock(side_effect=mock_gen)
            token = await self.task_mgr.start_request(self.user, req.id)
            res = await execute_generation_request(failed_req, self.storage, ai_mock, token, self.task_mgr)
            await self.task_mgr.finish_request(self.user, token)
            self.assertTrue(res.success)
            self.assertIn("Before & After", captured_prompts[0])
            self.assertIn("Education / Skills", captured_prompts[0])

            # Now test regeneration from successful script
            script = res.script
            captured_regen_prompts = []
            async def mock_regen(prompt, is_json=True):
                captured_regen_prompts.append(prompt)
                return self._make_valid_plan_json(60)

            ai_mock.generate_response = AsyncMock(side_effect=mock_regen)
            regen_token = await self.task_mgr.start_request(self.user, "regen_1")
            regen_res = await regenerate_script(
                user_key=self.user,
                script_id=script.id,
                version=script.version,
                storage=self.storage,
                ai=ai_mock,
                task_mgr=self.task_mgr,
                token=regen_token,
            )
            await self.task_mgr.finish_request(self.user, regen_token)
            self.assertTrue(regen_res.success)
            self.assertEqual(len(captured_regen_prompts), 1)
            self.assertIn("Before & After", captured_regen_prompts[0])
            self.assertIn("Education / Skills", captured_regen_prompts[0])

        asyncio.run(run_retry())

    # 7. Cache does not mix niches or formats
    def test_cache_does_not_mix_niches_or_formats(self):
        async def run_cache():
            ai_mock = MagicMock()
            ai_mock._is_error_response = MagicMock(return_value=False)
            call_count = [0]
            async def mock_gen(prompt, is_json=False):
                call_count[0] += 1
                return f"1. 🔥 គំនិតទី 1: Call_{call_count[0]}\n🎯 Hook: Hook_{call_count[0]}"

            ai_mock.generate_response = AsyncMock(side_effect=mock_gen)

            # Call A: Food + Myth
            b1, ideas1, _, _ = await get_or_generate_ideas(
                self.user, "🍜 Food / Cooking", self.storage, ai_mock, format_id="myth", force_ai_only=True
            )
            self.assertEqual(call_count[0], 1)

            # Call B: Same niche & format -> MUST reuse cache (call_count stays 1)
            b2, ideas2, _, _ = await get_or_generate_ideas(
                self.user, "🍜 Food / Cooking", self.storage, ai_mock, format_id="myth", force_ai_only=True
            )
            self.assertEqual(call_count[0], 1)
            self.assertEqual(ideas1[0].topic, ideas2[0].topic)

            # Call C: Same niche, DIFFERENT format (pov) -> MUST NOT reuse cache (call_count becomes 2)
            b3, ideas3, _, _ = await get_or_generate_ideas(
                self.user, "🍜 Food / Cooking", self.storage, ai_mock, format_id="pov", force_ai_only=True
            )
            self.assertEqual(call_count[0], 2)
            self.assertNotEqual(ideas1[0].topic, ideas3[0].topic)

            # Call D: DIFFERENT niche (coffee), same format (myth) -> MUST NOT reuse cache (call_count becomes 3)
            b4, ideas4, _, _ = await get_or_generate_ideas(
                self.user, "☕️ Coffee / Beverages", self.storage, ai_mock, format_id="myth", force_ai_only=True
            )
            self.assertEqual(call_count[0], 3)
            self.assertNotEqual(ideas1[0].topic, ideas4[0].topic)

        asyncio.run(run_cache())

    # 8. Changing niche invalidates incompatible drafts while preserving successful scripts
    def test_changing_niche_invalidates_drafts_preserving_scripts(self):
        # 1. Save an existing draft and an existing successful script
        draft = Draft(
            id="d_old_niche",
            revision=1,
            format_id="3whs",
            topic="Old topic",
            duration_seconds=60,
            audience="Old audience",
            current_step="review",
            owner=self.user,
            niche="Food / Cooking",
        )
        self.storage.save_draft(self.user, draft)

        plan = ScriptPlan(
            title="Saved Old Script",
            target_audience="General",
            hook="Hook",
            caption="Caption",
            hashtags=["#old"],
            cta="Share",
            target_duration_seconds=60,
            estimated_speaking_seconds=55.0,
            is_timeline_valid=True,
            validation_notes=[],
            scenes=[Scene(scene_number=1, start_seconds=0, end_seconds=60, spoken_text_km="អត្ថបទ")],
        )
        saved_script = SavedScript(
            id="s_success_1",
            version=1,
            owner=self.user,
            request_snapshot=GenerationRequest(
                id="req_s1",
                operation="create",
                owner=self.user,
                draft_snapshot=draft.to_dict(),
                pace_units_per_second=10.0,
            ),
            plan=plan,
            created_at=datetime.now(timezone.utc),
        )
        self.storage.save_successful_script(saved_script)

        # Confirm draft and script exist
        self.assertIsNotNone(self.storage.get_draft("d_old_niche"))
        self.assertIsNotNone(self.storage.get_last_successful_script(self.user))

        # 2. Change niche: triggers clear_incompatible_drafts
        self.storage.save_user_niche(self.user, "📱 Technology / AI")
        self.storage.clear_incompatible_drafts(self.user)

        # 3. Draft must be cleared
        self.assertIsNone(self.storage.get_draft("d_old_niche"))
        # 4. Successful script must STILL be preserved!
        preserved_script = self.storage.get_last_successful_script(self.user)
        self.assertIsNotNone(preserved_script)
        self.assertEqual(preserved_script.id, "s_success_1")
        self.assertEqual(preserved_script.plan.title, "Saved Old Script")

    # 9. Back navigation preserves niche, format, and entered topic
    def test_back_navigation_preserves_state(self):
        draft = Draft(
            id="d_nav_test",
            revision=1,
            format_id="hottake",
            topic="Why social media is changing retail",
            duration_seconds=60,
            audience="Business owners",
            current_step="review",
            owner=self.user,
            niche="🛍 Sales / Online Business",
        )
        self.storage.save_draft(self.user, draft)

        # Simulate user navigation stack: Format -> Topic -> Review
        navigation.go_to(self.user, Screens.FORMAT_SELECTION, draft_id=draft.id)
        navigation.go_to(self.user, Screens.TOPIC_INPUT, draft_id=draft.id)
        navigation.go_to(self.user, Screens.DRAFT_REVIEW, draft_id=draft.id)

        # Step back to TOPIC_INPUT
        prev_screen, state = navigation.go_back(self.user)
        self.assertEqual(prev_screen, Screens.TOPIC_INPUT)
        restored_draft = self.storage.get_draft(state.draft_id)
        self.assertEqual(restored_draft.niche, "🛍 Sales / Online Business")
        self.assertEqual(restored_draft.format_id, "hottake")
        self.assertEqual(restored_draft.topic, "Why social media is changing retail")

        # Step back to FORMAT_SELECTION
        prev_screen, state = navigation.go_back(self.user)
        self.assertEqual(prev_screen, Screens.FORMAT_SELECTION)
        restored_draft = self.storage.get_draft(state.draft_id)
        self.assertEqual(restored_draft.niche, "🛍 Sales / Online Business")
        self.assertEqual(restored_draft.format_id, "hottake")
        self.assertEqual(restored_draft.topic, "Why social media is changing retail")

if __name__ == "__main__":
    unittest.main()
