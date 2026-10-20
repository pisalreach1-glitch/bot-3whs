import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import pytz

import trend_sources
from trend_sources import (
    NewsItem,
    get_fresh_news_sources,
    parse_rss_xml,
    normalize_title,
    FEED_CACHE_TTL_SECONDS,
)
import ai_service
from ai_service import AIService, _DAILY_IDEAS_CACHE
from bot import split_message, is_error_response, send_daily_content

class TestNewsGroundingFeature(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Clear caches before each test
        trend_sources._FEED_CACHE.clear()
        ai_service._DAILY_IDEAS_CACHE.clear()

    # 1. Valid recent feed items
    def test_parse_rss_xml_valid_recent(self):
        now_utc = datetime.now(timezone.utc)
        recent_date_str = (now_utc - timedelta(hours=4)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>AI breakthrough transforms small business in 2026 - TechDaily</title>
                    <link>https://example.com/news/1</link>
                    <pubDate>{recent_date_str}</pubDate>
                </item>
            </channel>
        </rss>
        """.encode("utf-8")
        items = parse_rss_xml(xml_content, "TechDaily", now_utc)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.title, "AI breakthrough transforms small business in 2026")
        self.assertEqual(item.publisher, "TechDaily")
        self.assertEqual(item.url, "https://example.com/news/1")
        self.assertTrue(item.is_recent)
        self.assertIsNotNone(item.published_at)
        self.assertIsNotNone(item.published_at.tzinfo)

    # 2. Old items and missing publication dates
    def test_parse_rss_xml_old_and_missing_pubdate(self):
        now_utc = datetime.now(timezone.utc)
        old_date_str = (now_utc - timedelta(days=5)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Test Feed</title>
                <item>
                    <title>Old Story from Last Week</title>
                    <link>https://example.com/old</link>
                    <pubDate>{old_date_str}</pubDate>
                </item>
                <item>
                    <title>Story without any publication date</title>
                    <link>https://example.com/nodate</link>
                </item>
            </channel>
        </rss>
        """.encode("utf-8")
        items = parse_rss_xml(xml_content, "Old Publisher", now_utc)
        self.assertEqual(len(items), 2)
        old_item = items[0]
        self.assertFalse(old_item.is_recent)
        self.assertIsNotNone(old_item.published_at)

        nodate_item = items[1]
        self.assertFalse(nodate_item.is_recent)
        self.assertIsNone(nodate_item.published_at)

    # 3. Duplicate articles deduplication
    def test_deduplication(self):
        title1 = "Cambodia Digital Economy Grows Rapidly"
        title2 = "Cambodia Digital Economy Grows Rapidly!"
        self.assertEqual(normalize_title(title1), normalize_title(title2))

    # 4. Feed timeout or malformed XML handling
    async def test_malformed_xml_and_timeout(self):
        now_utc = datetime.now(timezone.utc)
        malformed = b"<rss><channel><item><title>Unclosed tag"
        items = parse_rss_xml(malformed, "Bad Pub", now_utc)
        self.assertEqual(items, [])

        with patch("trend_sources.httpx.AsyncClient.get", side_effect=Exception("ReadTimeout")):
            res = await get_fresh_news_sources(category="general")
            self.assertIsInstance(res, list)
            self.assertEqual(len(res), 0)

    # 5. Invented source IDs from Gemini
    async def test_invented_source_ids_validation(self):
        service = AIService()
        fake_items = [
            NewsItem(
                id=1,
                title="Cambodia e-commerce expands",
                url="https://example.com/cambodia-ecommerce",
                publisher="Cambodia News",
                published_at=datetime.now(timezone.utc),
                is_recent=True
            )
        ]

        # Gemini hallucinates source ID [99] which is not in news_items (only id 1 exists)
        hallucinated_ai_response = (
            "💡 **គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ**\n\n"
            "១. ប្រធានបទ៖ អាជីវកម្មអនឡាញ\n"
            "Hook៖ ហេតុអ្វីឆ្នាំនេះលក់អនឡាញពិបាក?\n"
            "ទម្រង់៖ 3WHs\n"
            "ប្រភព៖ [99]\n"
        )

        with patch("ai_service.get_fresh_news_sources", return_value=fake_items):
            with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = hallucinated_ai_response
                result = await service.generate_daily_ideas("ទូទៅ")
                # Because [99] is invalid and valid_refs is empty, service falls back to showing retrieved sources list openly
                self.assertIn("បញ្ជីព័ត៌មានថ្មីៗដែលបានទាញយកមកពិនិត្យ", result)
                self.assertIn("Cambodia e-commerce expands", result)
                self.assertIn("https://example.com/cambodia-ecommerce", result)

    # 6. Valid Gemini response with valid source IDs -> Python link building
    async def test_valid_source_id_link_building(self):
        service = AIService()
        fake_items = [
            NewsItem(
                id=1,
                title="Cambodia Tech Startup Funding 2026",
                url="https://example.com/tech-funding",
                publisher="TechAsia",
                published_at=datetime.now(timezone.utc),
                is_recent=True
            )
        ]

        valid_gemini_output = (
            "💡 **គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ**\n\n"
            "១. ប្រធានបទ៖ ឱកាសទាក់ទាញទុន Startup\n"
            "Hook៖ តើអ្នកដឹងទេថា Startup បច្ចេកវិទ្យាកំពុងទទួលបានទុនយ៉ាងច្រើន?\n"
            "ទម្រង់៖ 3WHs Hook Script\n"
            "ប្រភព៖ [1]\n"
        )

        with patch("ai_service.get_fresh_news_sources", return_value=fake_items):
            with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = valid_gemini_output
                result = await service.generate_daily_ideas("ទូទៅ")
                self.assertIn("គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ", result)
                # Verified Python link building
                self.assertIn("[TechAsia: Cambodia Tech Startup Funding 2026](https://example.com/tech-funding)", result)
                self.assertIn("ប្រភពព័ត៌មានយោងពិតប្រាកដ", result)

    # 7. Honest fallback when retrieval fails or no recent items
    async def test_honest_fallback_when_no_recent_items(self):
        service = AIService()
        # No recent items returned
        with patch("ai_service.get_fresh_news_sources", return_value=[]):
            with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = "គំនិតទូទៅពី AI..."
                result = await service.generate_daily_ideas("ទូទៅ")
                self.assertIn("គំនិតមាតិកាទូទៅពី AI", result)
                self.assertIn("មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ", result)

    # 8. Category mismatch honest fallback
    async def test_category_mismatch_fallback(self):
        service = AIService()
        # Category "កសិកម្ម" (agriculture) has no news evidence feed
        with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "គំនិតកសិកម្មទូទៅ..."
            result = await service.generate_daily_ideas("កសិកម្ម")
            self.assertIn("គំនិតមាតិកាទូទៅពី AI", result)
            self.assertIn("មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ", result)
            self.assertIn("កសិកម្ម", result)

    # 9. Cache reuse: date (Asia/Phnom_Penh) and category caching saves Gemini quota
    async def test_cache_reuse_saves_quota(self):
        service = AIService()
        mock_gen = AsyncMock(return_value="💡 គំនិតមាតិកាថ្ងៃនេះ")
        with patch("ai_service.get_fresh_news_sources", return_value=[]):
            with patch.object(service, "generate_response", mock_gen):
                res1 = await service.generate_daily_ideas("ទូទៅ")
                res2 = await service.generate_daily_ideas("ទូទៅ")
                self.assertEqual(res1, res2)
                # Gemini must only be called ONCE
                self.assertEqual(mock_gen.call_count, 1)

    # 10. AI error responses are NOT cached
    async def test_error_responses_not_cached(self):
        service = AIService()
        mock_gen = AsyncMock(side_effect=[
            "⚠️ ប្រព័ន្ធ AI មានបញ្ហា",
            "គំនិតមាតិកាជោគជ័យលើកទី ២"
        ])
        with patch("ai_service.get_fresh_news_sources", return_value=[]):
            with patch.object(service, "generate_response", mock_gen):
                err_res = await service.generate_daily_ideas("ទូទៅ")
                self.assertTrue(is_error_response(err_res))
                # Second call should retry because error was not cached
                succ_res = await service.generate_daily_ideas("ទូទៅ")
                self.assertFalse(is_error_response(succ_res))
                self.assertEqual(mock_gen.call_count, 2)

    # 11. One generation for multiple broadcast subscribers
    async def test_broadcast_generates_once_for_all_subscribers(self):
        import bot
        bot.subscribers = {111, 222, 333, 444}
        mock_bot = AsyncMock()
        mock_context = MagicMock()
        mock_context.bot = mock_bot

        with patch("bot.ai_service.generate_daily_ideas", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "គំនិតសម្រាប់ broadcast"
            await send_daily_content(mock_context)
            # generate_daily_ideas must be called exactly once
            mock_gen.assert_called_once_with("ទូទៅ")
            # All 4 subscribers received the message
            self.assertEqual(mock_bot.send_message.call_count, 4)

    # 12. Message splitting and fallback for long messages
    def test_message_splitting(self):
        long_text = "ក" * 5000
        chunks = split_message(long_text, max_length=4000)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)

if __name__ == "__main__":
    unittest.main()
