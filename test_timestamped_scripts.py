import math
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

import script_models
from script_models import (
    Scene,
    ScriptPlan,
    PlanResult,
    ValidationError,
    parse_duration_seconds,
    count_khmer_dialogue_units,
    estimate_speaking_duration,
    validate_and_build_plan,
    parse_and_validate_script_plan,
    format_script_for_telegram,
    DEFAULT_CHARS_PER_SECOND,
)
import ai_service
from ai_service import AIService
import trend_sources
from trend_sources import NewsItem, parse_rss_xml
import bot
from bot import (
    get_user_pace,
    set_user_pace,
    get_user_duration,
    set_user_duration,
    split_message,
    send_daily_content,
    pace_command,
    cancel_command,
    handle_message,
    button_callback_handler,
    is_request_current,
)

class TestTimestampedScriptsAndVisuals(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        trend_sources._FEED_CACHE.clear()
        ai_service._DAILY_IDEAS_CACHE.clear()
        bot.user_settings.clear()

    # 1. Valid plans for 60, 120, 180, and 300 seconds
    def test_all_four_selectable_durations_valid_plans(self):
        self.assertEqual(parse_duration_seconds("60 វិនាទី"), 60)
        self.assertEqual(parse_duration_seconds("2 នាទី"), 120)
        self.assertEqual(parse_duration_seconds("3 នាទី"), 180)
        self.assertEqual(parse_duration_seconds("5 នាទី"), 300)

        for dur in [60, 120, 180, 300]:
            half = dur // 2
            raw_json = json.dumps({
                "title": f"Video for {dur}s",
                "target_audience": "Creators",
                "hook": "Check this out",
                "caption": "Viral video",
                "hashtags": ["#viral"],
                "cta": "Follow for more",
                "scenes": [
                    {
                        "scene_number": 1,
                        "start_seconds": 0,
                        "end_seconds": half,
                        "spoken_text_km": "សួស្តីអ្នកទាំងអស់គ្នា",
                        "shot_size": "Close-Up",
                        "camera_action": "Static",
                        "visual_action": "Speaking to camera",
                        "on_screen_text_km": "Hook",
                        "editing_note": "Cut",
                        "audio_note": "Music"
                    },
                    {
                        "scene_number": 2,
                        "start_seconds": half,
                        "end_seconds": dur,
                        "spoken_text_km": "នេះជាដំណោះស្រាយ",
                        "shot_size": "Wide Shot",
                        "camera_action": "Pan Right",
                        "visual_action": "Showing screen",
                        "on_screen_text_km": "Solution",
                        "editing_note": "Zoom",
                        "audio_note": "Beat drop"
                    }
                ]
            })
            res = validate_and_build_plan(raw_json, target_duration_seconds=dur)
            self.assertTrue(res.success, f"Failed for duration {dur}: {res.error_message}")
            self.assertIsNotNone(res.plan)
            self.assertEqual(res.plan.target_duration_seconds, dur)
            self.assertTrue(res.plan.is_timeline_valid)
            self.assertEqual(len(res.plan.scenes), 2)

    # 2. Invalid JSON and top-level types (array, string, number, null)
    def test_invalid_json_and_toplevel_types(self):
        # Broken JSON syntax
        res1 = validate_and_build_plan("{invalid_json", 60)
        self.assertFalse(res1.success)
        self.assertIn("មិនត្រឹមត្រូវ", res1.formatted_text)

        # Top-level list
        res2 = validate_and_build_plan("[1, 2, 3]", 60)
        self.assertFalse(res2.success)
        self.assertIn("Top-level", res2.error_message)

        # Top-level string
        res3 = validate_and_build_plan('"just a string"', 60)
        self.assertFalse(res3.success)

        # Top-level null
        res4 = validate_and_build_plan("null", 60)
        self.assertFalse(res4.success)

        # Empty string
        res5 = validate_and_build_plan("", 60)
        self.assertFalse(res5.success)

    # 3. Invalid scene_number and field types
    def test_invalid_scene_number_and_field_types(self):
        base = {
            "title": "Test",
            "scenes": [
                {
                    "scene_number": True,  # boolean rejected as scene_number
                    "start_seconds": 0,
                    "end_seconds": 60,
                    "visual_action": "Action",
                    "shot_size": "Medium",
                    "camera_action": "Static"
                }
            ]
        }
        res = validate_and_build_plan(json.dumps(base), 60)
        self.assertFalse(res.success)
        self.assertIn("scene_number", res.error_message)

        # Non-string visual direction
        base["scenes"][0]["scene_number"] = 1
        base["scenes"][0]["visual_action"] = {"nested": "not_a_string"}
        res2 = validate_and_build_plan(json.dumps(base), 60)
        self.assertFalse(res2.success)
        self.assertIn("visual_action", res2.error_message)

        # Permitted empty dialogue for visual-only scenes
        base["scenes"][0]["visual_action"] = "B-roll panning"
        base["scenes"][0]["spoken_text_km"] = ""  # empty dialogue
        res3 = validate_and_build_plan(json.dumps(base), 60)
        self.assertTrue(res3.success)
        self.assertEqual(res3.plan.scenes[0].estimated_spoken_seconds, 0.0)

    # 4. Empty scenes or non-object scenes
    def test_empty_scenes_and_non_objects(self):
        # Empty scenes list
        res1 = validate_and_build_plan(json.dumps({"title": "Test", "scenes": []}), 60)
        self.assertFalse(res1.success)
        self.assertIn("ទទេ", res1.error_message)

        # Missing scenes
        res2 = validate_and_build_plan(json.dumps({"title": "Test"}), 60)
        self.assertFalse(res2.success)

        # Non-dict scene entry
        res3 = validate_and_build_plan(json.dumps({"title": "Test", "scenes": ["string_scene"]}), 60)
        self.assertFalse(res3.success)
        self.assertIn("Object", res3.error_message)

    # 5. Negative, fractional, boolean, and non-finite timestamps
    def test_invalid_timestamps_rejected(self):
        def make_plan(start, end):
            return json.dumps({
                "title": "Test",
                "scenes": [
                    {
                        "scene_number": 1,
                        "start_seconds": start,
                        "end_seconds": end,
                        "visual_action": "Action",
                        "shot_size": "Medium",
                        "camera_action": "Static"
                    }
                ]
            })

        # Boolean start timestamp
        res1 = validate_and_build_plan(make_plan(False, 60), 60)
        self.assertFalse(res1.success)
        self.assertIn("boolean", res1.error_message)

        # Fractional timestamp
        res2 = validate_and_build_plan(make_plan(0, 59.5), 60)
        self.assertFalse(res2.success)
        self.assertIn("ទសភាគ", res2.error_message)

        # Negative timestamp
        res3 = validate_and_build_plan(make_plan(-5, 60), 60)
        self.assertFalse(res3.success)
        self.assertIn("អវិជ្ជមាន", res3.error_message)

    # 6. Timeline validation: gaps, overlaps, wrong start, wrong end
    def test_timeline_errors_rejected(self):
        # Start after zero
        bad_start = json.dumps({
            "title": "Test",
            "scenes": [
                {"scene_number": 1, "start_seconds": 5, "end_seconds": 60, "visual_action": "A", "shot_size": "M", "camera_action": "S"}
            ]
        })
        self.assertFalse(validate_and_build_plan(bad_start, 60).success)

        # Gap between scenes
        gap_plan = json.dumps({
            "title": "Test",
            "scenes": [
                {"scene_number": 1, "start_seconds": 0, "end_seconds": 20, "visual_action": "A", "shot_size": "M", "camera_action": "S"},
                {"scene_number": 2, "start_seconds": 25, "end_seconds": 60, "visual_action": "A", "shot_size": "M", "camera_action": "S"}
            ]
        })
        res_gap = validate_and_build_plan(gap_plan, 60)
        self.assertFalse(res_gap.success)
        self.assertIn("Gap", res_gap.error_message)

        # Wrong end time (exceeds tolerance > 1s)
        wrong_end = json.dumps({
            "title": "Test",
            "scenes": [
                {"scene_number": 1, "start_seconds": 0, "end_seconds": 45, "visual_action": "A", "shot_size": "M", "camera_action": "S"}
            ]
        })
        self.assertFalse(validate_and_build_plan(wrong_end, 60).success)

    # 7. Regression test: 0-40 and 20-40 overlap for 60s video MUST be rejected
    def test_overlap_regression_0_40_and_20_40(self):
        overlap_plan = json.dumps({
            "title": "Overlap Video",
            "scenes": [
                {
                    "scene_number": 1,
                    "start_seconds": 0,
                    "end_seconds": 40,
                    "visual_action": "Scene 1",
                    "shot_size": "Medium",
                    "camera_action": "Static"
                },
                {
                    "scene_number": 2,
                    "start_seconds": 20,
                    "end_seconds": 40,
                    "visual_action": "Scene 2",
                    "shot_size": "Close-Up",
                    "camera_action": "Pan"
                }
            ]
        })
        res = validate_and_build_plan(overlap_plan, 60)
        self.assertFalse(res.success, "0-40 and 20-40 overlap must be strictly rejected")
        self.assertIn("Overlap", res.error_message)

    # 8. Recalculation after narrow permitted timing adjustment (<= 1s at final scene)
    def test_recalculation_after_narrow_adjustment(self):
        # Continuous plan ending at 59s for target 60s (diff = +1s)
        plan_59s = json.dumps({
            "title": "Adjusted Video",
            "scenes": [
                {
                    "scene_number": 1,
                    "start_seconds": 0,
                    "end_seconds": 30,
                    "spoken_text_km": "ពាក្យប្លង់ទីមួយ",
                    "visual_action": "A",
                    "shot_size": "M",
                    "camera_action": "S"
                },
                {
                    "scene_number": 2,
                    "start_seconds": 30,
                    "end_seconds": 59,  # Ends at 59s, 1s shy of 60s
                    "spoken_text_km": "ពាក្យប្លង់ទីពីរ",
                    "visual_action": "B",
                    "shot_size": "M",
                    "camera_action": "S"
                }
            ]
        })
        res = validate_and_build_plan(plan_59s, 60, user_pace=10.0)
        self.assertTrue(res.success)
        self.assertEqual(res.plan.scenes[1].end_seconds, 60)  # Narrowly adjusted
        self.assertTrue(any("កែសម្រួល" in n for n in res.validation_notes))
        # Speaking estimates and warnings recalculated
        self.assertGreater(res.plan.scenes[1].estimated_spoken_seconds, 0)
        self.assertFalse(res.plan.scenes[1].is_dialogue_too_long)

    # 9. Khmer text character units (not WPM or syllable claims)
    def test_khmer_character_units(self):
        khmer_text = "នេះជាអត្ថបទគំរូសាកល្បងភាសាខ្មែរគ្មានដកឃ្លា"
        units = count_khmer_dialogue_units(khmer_text)
        self.assertGreater(units, 20)
        est = estimate_speaking_duration(khmer_text, chars_per_second=10.0)
        self.assertGreater(est, 2.0)

    # 10. /pace command validation: NaN, inf, invalid seconds, bounds
    async def test_pace_command_validation(self):
        chat_id = 12345
        mock_update = MagicMock()
        mock_update.effective_chat.id = chat_id
        mock_msg = AsyncMock()
        del mock_msg.message
        mock_update.message = mock_msg
        mock_context = MagicMock()

        # NaN seconds
        mock_context.args = ["NaN", "សួស្តីអ្នកទាំងអស់គ្នា"]
        await pace_command(mock_update, mock_context)
        self.assertIn("មិនត្រឹមត្រូវ", mock_msg.reply_text.call_args[0][0])

        # Negative seconds
        mock_context.args = ["-10", "សួស្តីអ្នកទាំងអស់គ្នា"]
        await pace_command(mock_update, mock_context)
        self.assertIn("ចន្លោះពី", mock_msg.reply_text.call_args[0][0])

        # Short sample text (< 10 units)
        mock_context.args = ["10", "ខ្លី"]
        await pace_command(mock_update, mock_context)
        self.assertIn("ខ្លីពេក", mock_msg.reply_text.call_args[0][0])

        # Too slow (< 3 chars/sec) -> explains without silent deceptive clamping
        mock_context.args = ["100", "សួស្តីអ្នកទាំងអស់គ្នា " * 2]
        await pace_command(mock_update, mock_context)
        self.assertIn("យឺតខ្លាំងខុសធម្មតា", mock_msg.reply_text.call_args[0][0])

        # Valid pace
        mock_context.args = ["10", "សួស្តីអ្នកទាំងអស់គ្នា ថ្ងៃនេះខ្ញុំមានគន្លឹះពិសេស " * 2]
        await pace_command(mock_update, mock_context)
        self.assertIn("ជោគជ័យ", mock_msg.reply_text.call_args[0][0])
        self.assertIn("ការប៉ាន់ស្មានប្រហាក់ប្រហែល", mock_msg.reply_text.call_args[0][0])

    # 11. Invalid initial generation does not mutate state or show success
    async def test_invalid_initial_generation_does_not_mutate_state(self):
        mock_update = MagicMock()
        mock_update.effective_chat.id = 777
        mock_msg = AsyncMock()
        del mock_msg.message
        mock_msg.text = "ប្រធានបទសាកល្បង"
        mock_status_msg = AsyncMock()
        mock_msg.reply_text.return_value = mock_status_msg
        mock_update.message = mock_msg

        mock_context = MagicMock()
        mock_context.user_data = {
            "state": "awaiting_topic",
            "content_type": "3whs",
            "is_processing": False,
            "req_token": 0,
        }

        # AI returns invalid plan (e.g. overlap 0-40 and 20-40)
        invalid_plan_result = PlanResult(
            success=False,
            plan=None,
            formatted_text="⚠️ Plan validation failed",
            error_message="Overlap",
        )

        with patch("bot.ai_service.generate_content_by_type", new_callable=AsyncMock, return_value=invalid_plan_result):
            await handle_message(mock_update, mock_context)

        # Must not store in last_script or last_script_plan
        self.assertNotIn("last_script", mock_context.user_data)
        self.assertNotIn("last_script_plan", mock_context.user_data)
        # Must show failure/incomplete notice, not success notice
        last_reply = mock_msg.reply_text.call_args[0][0]
        self.assertIn("មិនទាន់ជោគជ័យ", last_reply)
        self.assertNotIn("រួចរាល់!", last_reply)

    # 12. Invalid refinement preserves previous script and metadata
    async def test_invalid_refinement_preserves_previous_script(self):
        mock_query = AsyncMock()
        mock_query.data = "refine:shorten"
        mock_status_msg = AsyncMock()
        mock_query.message.reply_text.return_value = mock_status_msg
        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        mock_update.effective_chat.id = 888

        prev_plan = ScriptPlan(
            title="Old Plan", target_audience="", hook="", caption="",
            hashtags=[], cta="", target_duration_seconds=60,
            estimated_speaking_seconds=40.0, scenes=[]
        )
        mock_context = MagicMock()
        mock_context.user_data = {
            "last_script": "ORIGINAL_GOOD_SCRIPT",
            "last_script_plan": prev_plan,
            "last_duration": "60 វិនាទី",
            "is_processing": False,
            "req_token": 0,
        }

        # Refinement returns failure
        failure_result = PlanResult(
            success=False,
            plan=None,
            formatted_text="⚠️ Shortening Failed",
            error_message="Validation error"
        )

        with patch("bot.ai_service.refine_shorten", new_callable=AsyncMock, return_value=failure_result):
            await button_callback_handler(mock_update, mock_context)

        # Previous script and plan must be PRESERVED
        self.assertEqual(mock_context.user_data["last_script"], "ORIGINAL_GOOD_SCRIPT")
        self.assertEqual(mock_context.user_data["last_script_plan"], prev_plan)
        # Failure notice shown
        self.assertIn("មិនទាន់ជោគជ័យ", mock_query.message.reply_text.call_args[0][0])

    # 13. Cancellation and stale-result suppression
    async def test_cancel_and_stale_result_suppression(self):
        mock_update = MagicMock()
        mock_update.effective_chat.id = 999
        mock_msg = AsyncMock()
        del mock_msg.message
        mock_update.message = mock_msg

        # Mock an active running task
        mock_task = MagicMock()
        mock_task.done.return_value = False

        mock_context = MagicMock()
        mock_context.user_data = {
            "is_processing": True,
            "req_token": 5,
            "active_task": mock_task,
            "last_script": "EXISTING_SCRIPT",
        }

        # Run /cancel
        await cancel_command(mock_update, mock_context)

        # Active task was cancelled
        mock_task.cancel.assert_called_once()
        # Request token was incremented (invalidating in-flight token 5)
        self.assertEqual(mock_context.user_data["req_token"], 6)
        # Previous script strictly preserved
        self.assertEqual(mock_context.user_data["last_script"], "EXISTING_SCRIPT")
        self.assertFalse(mock_context.user_data["is_processing"])

        # Verify that checking token 5 is now considered stale
        self.assertFalse(is_request_current(mock_context, 5))

    # 14. Message splitting for long texts
    def test_message_splitting(self):
        long_text = "ប្លង់ទី ១៖ ខ្លឹមសារវែង " * 300
        chunks = split_message(long_text, max_length=4000)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)

    # 15. Duplicate simultaneous user requests
    async def test_duplicate_simultaneous_user_requests(self):
        from bot import acquire_user_request, release_user_request
        mock_ctx = MagicMock()
        mock_ctx.user_data = {}

        # First request acquires lock
        token1 = acquire_user_request(mock_ctx)
        self.assertIsNotNone(token1)
        self.assertTrue(mock_ctx.user_data["is_processing"])

        # Second simultaneous request is rejected
        token2 = acquire_user_request(mock_ctx)
        self.assertIsNone(token2, "Second concurrent request must be rejected")

        # After releasing first, new request can be acquired
        release_user_request(mock_ctx, token1)
        self.assertFalse(mock_ctx.user_data["is_processing"])
        token3 = acquire_user_request(mock_ctx)
        self.assertIsNotNone(token3)

    # 16. Timeout halts fallback to prevent quota waste
    async def test_timeout_stops_fallback_cascade(self):
        service = AIService()
        # Mock _generate_with_model to timeout on gemini-2.5-flash
        call_models = []
        async def fake_generate_with_model(model_name, prompt, is_json):
            call_models.append(model_name)
            raise asyncio.TimeoutError()

        with patch.object(service, "is_configured", return_value=True):
            with patch.object(service, "_generate_with_model", side_effect=fake_generate_with_model):
                res = await service.generate_response("test prompt")
                # Must stop immediately on timeout without cascading to all models
                self.assertEqual(len(call_models), 1)
                self.assertIn("Request Timeout", res)

    # 17. Scheduler configuration check when JobQueue is unavailable
    def test_scheduler_jobqueue_unavailable_warning(self):
        with patch("bot.ApplicationBuilder") as mock_app_builder:
            mock_app = MagicMock()
            mock_app.job_queue = None  # Simulate JobQueue missing
            mock_app_builder.return_value.token.return_value.concurrent_updates.return_value.build.return_value = mock_app

            with patch("bot.logger.error") as mock_log_err:
                with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "mock_token"}):
                    # Mock run_polling to exit immediately
                    mock_app.run_polling.side_effect = SystemExit(0)
                    try:
                        bot.main()
                    except SystemExit:
                        pass
                    # Verify actionable error message logged
                    self.assertTrue(mock_log_err.called)
                    error_msg = mock_log_err.call_args[0][0]
                    self.assertIn("JobQueue is NOT available", error_msg)
                    self.assertIn("python-telegram-bot[job-queue]", error_msg)

if __name__ == "__main__":
    unittest.main()
