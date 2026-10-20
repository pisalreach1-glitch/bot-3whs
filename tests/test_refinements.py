"""
tests/test_refinements.py - Tests for Shorten, Regenerate, Hook generation/application, and zero-AI view switching.
"""

import json
import tempfile
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.models import (
    UserKey,
    Draft,
    GenerationRequest,
    SavedScript,
    ScriptPlan,
    Scene,
    ErrorCodes,
)
from app.storage import Storage
from app.task_manager import TaskManager
from app.services.refinements import (
    shorten_script,
    regenerate_script,
    generate_hook_options,
    apply_hook_option,
)
from app.views import (
    render_script_summary,
    render_script_read,
    render_script_shots,
    render_script_caption,
)

class TestRefinements(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_refinements.sqlite3"
        self.storage = Storage(db_path=self.db_path)
        self.task_mgr = TaskManager()
        self.user = UserKey(chat_id=123, user_id=456)

        # Create initial saved script (v1)
        self.initial_scene = Scene(
            scene_number=1,
            start_seconds=0,
            end_seconds=60,
            spoken_text_km="សួស្តី! នេះជាមេរៀនសង្ខេបដំបូង។",
            shot_size="Medium",
            camera_action="Static",
            visual_action="Host smiling",
            on_screen_text_km="Lesson 1",
            editing_note="Direct cut",
            audio_note="Upbeat background",
            estimated_spoken_seconds=2.5,
        )
        self.initial_plan = ScriptPlan(
            title="Shorten Test Script",
            target_audience="Students",
            hook="Hook text",
            caption="Caption text",
            hashtags=["#learn"],
            cta="Subscribe",
            target_duration_seconds=60,
            estimated_speaking_seconds=2.5,
            scenes=[self.initial_scene],
        )
        self.draft = Draft(
            id="d_test",
            revision=1,
            format_id="3whs",
            topic="Study Tips",
            duration_seconds=60,
            audience="Students",
        )
        self.initial_req = GenerationRequest(
            id="req_orig",
            operation="create",
            owner=self.user,
            draft_snapshot=self.draft.to_snapshot(),
            pace_units_per_second=10.0,
        )
        self.script_v1 = SavedScript(
            id="script_target",
            version=1,
            owner=self.user,
            request_snapshot=self.initial_req,
            plan=self.initial_plan,
            created_at=datetime.now(timezone.utc),
        )
        self.storage.save_successful_script(self.script_v1)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def _async_test_shorten_creates_version_2(self):
        ai_mock = MagicMock()
        ai_mock._is_error_response = MagicMock(return_value=False)
        shortened_json = json.dumps({
            "title": "Shortened Script",
            "target_audience": "Students",
            "hook": "Concise Hook",
            "caption": "Short caption",
            "hashtags": ["#quick"],
            "cta": "Share",
            "scenes": [
                {
                    "scene_number": 1,
                    "start_seconds": 0,
                    "end_seconds": 60,
                    "spoken_text_km": "សង្ខេបខ្លីខ្លឹម",
                    "shot_size": "Close-up",
                    "camera_action": "Static",
                    "visual_action": "Host speaking quickly",
                    "on_screen_text_km": "Quick Tips",
                    "editing_note": "Cut",
                    "audio_note": "Fast",
                }
            ]
        })
        ai_mock.generate_response = AsyncMock(return_value=shortened_json)

        token = await self.task_mgr.start_request(self.user, "shorten_1")
        result = await shorten_script(
            user_key=self.user,
            script_id="script_target",
            version=1,
            storage=self.storage,
            ai=ai_mock,
            task_mgr=self.task_mgr,
            token=token,
        )
        await self.task_mgr.finish_request(self.user, token)

        self.assertTrue(result.success)
        self.assertEqual(result.script.version, 2)
        self.assertEqual(result.script.id, "script_target")

        # Verify v1 is still intact in storage
        v1 = self.storage.get_script("script_target", 1)
        self.assertIsNotNone(v1)
        self.assertEqual(v1.plan.title, "Shorten Test Script")

        # Verify v2 is retrieved
        v2 = self.storage.get_script("script_target", 2)
        self.assertIsNotNone(v2)
        self.assertEqual(v2.plan.title, "Shortened Script")

    def test_shorten_creates_version_2(self):
        asyncio.run(self._async_test_shorten_creates_version_2())

    async def _async_test_hook_generation_and_safe_application(self):
        ai_mock = MagicMock()
        ai_mock._is_error_response = MagicMock(return_value=False)
        ai_mock.generate_response = AsyncMock(return_value="""
✨ **ជម្រើសទី 1 (Curiosity Hook)**:
🗣️ **ពាក្យនិយាយ**: "តើអ្នកដឹងទេថា វិធីសន្សំប្រាក់មួយនេះងាយស្រួលបំផុត?"
🎥 **កាយវិការ**: ចង្អុលដៃ

⚠️ **ជម្រើសទី 2 (Warning Hook)**:
🗣️ **ពាក្យនិយាយ**: "ឈប់ធ្វើបែបនេះភ្លាម ប្រសិនបើមិនចង់ស្តាយក្រោយ!"
🎥 **កាយវិការ**: លើកដៃឃាត់

🎯 **ជម្រើសទី 3 (Direct Value Hook)**:
🗣️ **ពាក្យនិយាយ**: "នេះជាគន្លឹះ ៣ យ៉ាងជួយបង្កើនប្រាក់ចំណូលរបស់អ្នក!"
🎥 **កាយវិការ**: ទឹកមុខជឿជាក់
""")

        # 1. Generate hook options
        token, hooks, err = await generate_hook_options(
            user_key=self.user,
            script_id="script_target",
            version=1,
            storage=self.storage,
            ai=ai_mock,
        )
        self.assertIsNotNone(token)
        self.assertEqual(len(hooks), 3)
        self.assertIsNone(err)

        # 2. Applying Option #1 updates opening dialogue in a new version (v2)
        res = apply_hook_option(
            user_key=self.user,
            script_id="script_target",
            version=1,
            option_index=1,
            options_token=token,
            storage=self.storage,
        )
        self.assertTrue(res.success)
        self.assertEqual(res.script.version, 2)
        self.assertEqual(res.script.plan.scenes[0].spoken_text_km, "តើអ្នកដឹងទេថា វិធីសន្សំប្រាក់មួយនេះងាយស្រួលបំផុត?")

        # 3. Excessive hook length (>1.8x scene duration) rejects and preserves original
        excessive_token = "h_excessive"
        long_hook = [{"type": "Long", "spoken_text": "ពាក្យនិយាយ " * 200, "visual": ""}]
        self.storage.save_hook_options(excessive_token, "script_target", 1, long_hook)

        res_rej = apply_hook_option(
            user_key=self.user,
            script_id="script_target",
            version=1,
            option_index=1,
            options_token=excessive_token,
            storage=self.storage,
        )
        self.assertFalse(res_rej.success)
        self.assertEqual(res_rej.error_code, ErrorCodes.INVALID_TIMELINE)
        self.assertIn("Script ដើមត្រូវបានរក្សាទុកដដែល", res_rej.user_message_km)

    def test_hook_generation_and_safe_application(self):
        asyncio.run(self._async_test_hook_generation_and_safe_application())

    def test_view_switching_makes_zero_ai_calls(self):
        """All 4 script views render directly from SavedScript with 0 AI involvement."""
        ai_mock = MagicMock()

        summary_text = render_script_summary(self.script_v1, pace=10.0)
        self.assertIn("Shorten Test Script", summary_text)
        self.assertIn("Students", summary_text)

        read_text = render_script_read(self.script_v1)
        self.assertIn("សួស្តី! នេះជាមេរៀនសង្ខេបដំបូង។", read_text)
        self.assertIn("ប្លង់ទី 1", read_text)

        shots_text = render_script_shots(self.script_v1, pace=10.0)
        self.assertIn("Medium", shots_text)
        self.assertIn("Host smiling", shots_text)
        self.assertIn("Lesson 1", shots_text)

        caption_text = render_script_caption(self.script_v1)
        self.assertIn("Caption text", caption_text)
        self.assertIn("#learn", caption_text)

        # AI mock was NEVER touched
        ai_mock.generate_response.assert_not_called()
        self.assertEqual(ai_mock.call_count, 0)

if __name__ == "__main__":
    unittest.main()
