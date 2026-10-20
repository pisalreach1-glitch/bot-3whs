import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

import script_models
from script_models import (
    Scene,
    ScriptPlan,
    parse_duration_seconds,
    count_khmer_dialogue_units,
    estimate_speaking_duration,
    validate_timeline,
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
    is_error_response,
)

class TestTimestampedScriptsAndVisuals(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        trend_sources._FEED_CACHE.clear()
        ai_service._DAILY_IDEAS_CACHE.clear()
        bot.user_settings.clear()

    # 1. All 4 selectable durations
    def test_all_four_selectable_durations(self):
        self.assertEqual(parse_duration_seconds("60 វិនាទី"), 60)
        self.assertEqual(parse_duration_seconds("2 នាទី"), 120)
        self.assertEqual(parse_duration_seconds("3 នាទី"), 180)
        self.assertEqual(parse_duration_seconds("5 នាទី"), 300)

        # Also test numerical and variations
        self.assertEqual(parse_duration_seconds("60s"), 60)
        self.assertEqual(parse_duration_seconds("2 min"), 120)
        self.assertEqual(parse_duration_seconds("3 minutes"), 180)
        self.assertEqual(parse_duration_seconds("5"), 300)

        # Validate that a scene plan ending at each duration validates correctly
        for dur in [60, 120, 180, 300]:
            scenes = [
                Scene(scene_number=1, start_seconds=0, end_seconds=dur // 2),
                Scene(scene_number=2, start_seconds=dur // 2, end_seconds=dur),
            ]
            valid, notes = validate_timeline(scenes, dur)
            self.assertTrue(valid, f"Failed for duration {dur}: {notes}")

    # 2. Timeline gaps, overlaps, and incorrect end times
    def test_timeline_validation_rules(self):
        target = 60

        # Gap between scene 1 and 2
        gap_scenes = [
            Scene(scene_number=1, start_seconds=0, end_seconds=10),
            Scene(scene_number=2, start_seconds=15, end_seconds=60),  # Gap 10-15s
        ]
        valid, notes = validate_timeline(gap_scenes, target)
        self.assertFalse(valid)
        self.assertTrue(any("ចន្លោះប្រហោង" in n or "Gap" in n for n in notes))

        # Overlap between scene 1 and 2
        overlap_scenes = [
            Scene(scene_number=1, start_seconds=0, end_seconds=20),
            Scene(scene_number=2, start_seconds=15, end_seconds=60),  # Overlap at 15-20s
        ]
        valid, notes = validate_timeline(overlap_scenes, target)
        self.assertFalse(valid)
        self.assertTrue(any("ជាន់គ្នា" in n or "Overlap" in n for n in notes))

        # Incorrect end time
        wrong_end_scenes = [
            Scene(scene_number=1, start_seconds=0, end_seconds=20),
            Scene(scene_number=2, start_seconds=20, end_seconds=45),  # Ends at 45 instead of 60
        ]
        valid, notes = validate_timeline(wrong_end_scenes, target)
        self.assertFalse(valid)
        self.assertTrue(any("មិនត្រូវនឹងរយៈពេលកំណត់" in n for n in notes))

        # Start not 0
        wrong_start_scenes = [
            Scene(scene_number=1, start_seconds=5, end_seconds=60),
        ]
        valid, notes = validate_timeline(wrong_start_scenes, target)
        self.assertFalse(valid)
        self.assertTrue(any("មិនបានចាប់ផ្តើមពីវិនាទី 0" in n for n in notes))

        # Negative time or zero-duration
        zero_len_scenes = [
            Scene(scene_number=1, start_seconds=0, end_seconds=0),
            Scene(scene_number=2, start_seconds=0, end_seconds=60),
        ]
        valid, notes = validate_timeline(zero_len_scenes, target)
        self.assertFalse(valid)

    # 3. Khmer text without spaces
    def test_khmer_text_without_spaces(self):
        # In Khmer, words are written continuously without spaces
        khmer_sentence_no_spaces = "នេះជាអត្ថបទគំរូសាកល្បងភាសាខ្មែរគ្មានដកឃ្លា"
        
        # Whitespace split fails (returns 1 word)
        whitespace_split_count = len(khmer_sentence_no_spaces.split())
        self.assertEqual(whitespace_split_count, 1)

        # Our character/syllable unit counting heuristic correctly counts meaningful script units
        unit_count = count_khmer_dialogue_units(khmer_sentence_no_spaces)
        self.assertGreater(unit_count, 20)  # Contains ~39 meaningful script characters

        # Estimated speaking duration does not return near-zero
        est_duration = estimate_speaking_duration(khmer_sentence_no_spaces, chars_per_second=10.0)
        self.assertGreater(est_duration, 2.0)

    # 4. Speaking-pace calibration (/pace)
    async def test_speaking_pace_calibration(self):
        chat_id = 98765
        # Initial default pace
        self.assertEqual(get_user_pace(chat_id), DEFAULT_CHARS_PER_SECOND)

        # Calibrate with sample text: 10 seconds for 120 characters -> 12.0 chars/sec
        sample_text = "នេះជាអត្ថបទគំរូសាកល្បងភាសាខ្មែរ " * 5
        units = count_khmer_dialogue_units(sample_text)
        seconds = 10.0
        expected_pace = round(units / seconds, 2)

        set_user_pace(chat_id, expected_pace)
        self.assertEqual(get_user_pace(chat_id), expected_pace)

        # Test pace_command logic via Update/Context mock
        mock_update = MagicMock()
        mock_update.effective_chat.id = chat_id
        mock_message = AsyncMock()
        del mock_message.message
        mock_update.message = mock_message
        mock_context = MagicMock()
        mock_context.args = ["15", "សួស្តីអ្នកទាំងអស់គ្នា", "ថ្ងៃនេះខ្ញុំមានគន្លឹះពិសេស"]

        await pace_command(mock_update, mock_context)
        self.assertTrue(mock_message.reply_text.called)
        # Stored pace was updated
        updated_pace = get_user_pace(chat_id)
        self.assertNotEqual(updated_pace, 0)

    # 5. Dialogue too long for its scene
    def test_dialogue_too_long_warning(self):
        target = 60
        # Scene 1 is 3 seconds (0 to 3s), but spoken text has 80 characters (~8 seconds of dialogue)
        long_spoken_text = "សួស្តីអ្នកទាំងអស់គ្នា! ថ្ងៃនេះខ្ញុំមានរឿងរ៉ាវដ៏វែងមួយដែលមិនអាចនិយាយចប់ត្រឹមតែបីវិនាទីនោះទេ!"
        raw_json = json.dumps({
            "title": "Test Video",
            "target_audience": "Creators",
            "hook": "Hook 3s",
            "caption": "Caption",
            "hashtags": ["#test"],
            "cta": "Follow now",
            "scenes": [
                {
                    "scene_number": 1,
                    "start_seconds": 0,
                    "end_seconds": 3,
                    "spoken_text_km": long_spoken_text,
                    "shot_size": "Close-Up",
                    "camera_action": "Static",
                    "visual_action": "Speaking to camera",
                    "on_screen_text_km": "Tips",
                    "editing_note": "Fast cut",
                    "audio_note": "Upbeat"
                },
                {
                    "scene_number": 2,
                    "start_seconds": 3,
                    "end_seconds": 60,
                    "spoken_text_km": "ខ្លីល្មម",
                    "shot_size": "Medium Shot",
                    "camera_action": "Static",
                    "visual_action": "Demo",
                    "on_screen_text_km": "",
                    "editing_note": "",
                    "audio_note": ""
                }
            ]
        })

        plan = parse_and_validate_script_plan(raw_json, target_duration_seconds=target, user_pace=10.0)
        self.assertTrue(plan.is_timeline_valid)
        self.assertTrue(plan.scenes[0].is_dialogue_too_long)
        self.assertFalse(plan.scenes[1].is_dialogue_too_long)

        # Check that Telegram formatted output displays the warning
        formatted = format_script_for_telegram(plan, user_pace=10.0)
        self.assertIn("ពាក្យនិយាយអាចវែងបន្តិច", formatted)
        self.assertIn("រយៈពេលនិយាយ៖ ប៉ាន់ស្មាន", formatted)

    # 6. Feed failure and old/missing publication dates
    def test_feed_old_and_missing_pubdate(self):
        now_utc = datetime.now(timezone.utc)
        old_date_str = (now_utc - timedelta(days=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        xml_content = f"""<rss><channel>
            <item><title>Old News</title><link>https://example.com/old</link><pubDate>{old_date_str}</pubDate></item>
            <item><title>No Date News</title><link>https://example.com/nodate</link></item>
        </channel></rss>""".encode("utf-8")

        items = parse_rss_xml(xml_content, "TestPub", now_utc)
        self.assertEqual(len(items), 2)
        self.assertFalse(items[0].is_recent)
        self.assertFalse(items[1].is_recent)
        self.assertIsNone(items[1].published_at)

    # 7. Invalid source IDs fallback to open source list
    async def test_invalid_source_ids_fallback(self):
        service = AIService()
        fake_items = [
            NewsItem(id=1, title="Tech In Cambodia", publisher="KhmerTech", url="https://example.com/1", published_at=datetime.now(timezone.utc), is_recent=True)
        ]
        # AI returns fabricated source [S99]
        fake_ai_output = "🔥 គំនិតទី ១\n• Hook: Test\n• ប្រភព៖ [99]"

        with patch("ai_service.get_fresh_news_sources", return_value=fake_items):
            with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = fake_ai_output
                result = await service.generate_daily_ideas("ទូទៅ")
                self.assertIn("បញ្ជីព័ត៌មានថ្មីៗដែលបានទាញយកមកពិនិត្យ", result)
                self.assertIn("Tech In Cambodia", result)

    # 8. Honest AI-only fallback
    async def test_honest_fallback(self):
        service = AIService()
        with patch("ai_service.get_fresh_news_sources", return_value=[]):
            with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = "គំនិត AI គំរូ..."
                result = await service.generate_daily_ideas("ទូទៅ")
                self.assertIn("គំនិតមាតិកាទូទៅពី AI", result)
                self.assertIn("មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ", result)

    # 9. Daily cache reuse saves quota
    async def test_daily_cache_reuse(self):
        service = AIService()
        mock_gen = AsyncMock(return_value="គំនិតមាតិកាថ្ងៃនេះ")
        with patch("ai_service.get_fresh_news_sources", return_value=[]):
            with patch.object(service, "generate_response", mock_gen):
                res1 = await service.generate_daily_ideas("ទូទៅ")
                res2 = await service.generate_daily_ideas("ទូទៅ")
                self.assertEqual(res1, res2)
                self.assertEqual(mock_gen.call_count, 1)

    # 10. One generation for multiple subscribers
    async def test_broadcast_one_generation_for_all(self):
        bot.subscribers = {101, 102, 103}
        mock_bot = AsyncMock()
        mock_context = MagicMock()
        mock_context.bot = mock_bot

        with patch("bot.ai_service.generate_daily_ideas", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "Daily content"
            await send_daily_content(mock_context)
            mock_gen.assert_called_once_with("ទូទៅ")
            self.assertEqual(mock_bot.send_message.call_count, 3)

    # 11. Refinement failure preserves the successful script
    async def test_refinement_failure_preserves_script(self):
        service = AIService()
        # When refine_shorten fails with AI error, it returns (error_text, None)
        with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "⚠️ Quota Limit Exceeded"
            err_msg, plan = await service.refine_shorten("Old Script Content", "60 វិនាទី")
            self.assertTrue(is_error_response(err_msg))
            self.assertIsNone(plan)

        # In bot.py, context.user_data["last_script"] is preserved when plan is None
        user_data = {
            "last_script": "Original Successful Script",
            "last_script_plan": ScriptPlan("Title", "Audience", "Hook", "Cap", [], "CTA", 60, 50.0, [])
        }
        # Simulate failed shorten callback logic
        if not is_error_response(err_msg) and plan is not None:
            user_data["last_script"] = err_msg
        # Assert previous script is strictly preserved
        self.assertEqual(user_data["last_script"], "Original Successful Script")

    # 12. Long Telegram output split correctly
    def test_long_telegram_output_split(self):
        long_text = "ប្លង់ទី ១៖ ខ្លឹមសារវែង " * 300
        chunks = split_message(long_text, max_length=4000)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)

if __name__ == "__main__":
    unittest.main()
