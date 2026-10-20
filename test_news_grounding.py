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
    is_item_relevant_to_category,
    fetch_single_feed,
    MAX_FEED_BYTES,
    FEED_CACHE_TTL_SECONDS,
)
import ai_service
from ai_service import AIService, _DAILY_IDEAS_CACHE
import bot
from bot import split_message, send_daily_content

class TestNewsGroundingFeature(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        trend_sources._FEED_CACHE.clear()
        ai_service._DAILY_IDEAS_CACHE.clear()

    # 1. Category keyword word-boundary matching (prevents false positives like 'said' matching 'ai')
    def test_category_keyword_word_boundaries_no_false_positives(self):
        item_said = NewsItem(id=1, title="President said economy is growing", publisher="News", url="http://a.com")
        item_detail = NewsItem(id=2, title="Details emerge about the new policy", publisher="News", url="http://b.com")
        item_chair = NewsItem(id=3, title="The chair of committee spoke yesterday", publisher="News", url="http://c.com")

        # None of these should match 'tech' (which contains keyword 'ai')
        self.assertFalse(is_item_relevant_to_category(item_said, "tech"))
        self.assertFalse(is_item_relevant_to_category(item_detail, "tech"))
        self.assertFalse(is_item_relevant_to_category(item_chair, "tech"))

        # Actual tech keywords should match
        item_real_ai = NewsItem(id=4, title="New AI model released by research lab", publisher="News", url="http://d.com")
        item_software = NewsItem(id=5, title="Major software update rolled out", publisher="News", url="http://e.com")
        self.assertTrue(is_item_relevant_to_category(item_real_ai, "tech"))
        self.assertTrue(is_item_relevant_to_category(item_software, "tech"))

        # Business keywords
        item_market = NewsItem(id=6, title="Stock market reaches record high", publisher="News", url="http://f.com")
        self.assertTrue(is_item_relevant_to_category(item_market, "business"))

    # 2. Google News <source> actual publisher extraction
    def test_google_news_publisher_extraction(self):
        now_utc = datetime.now(timezone.utc)
        recent_date_str = (now_utc - timedelta(hours=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        xml_content = f"""<rss><channel>
            <item>
                <title>Cambodia Digital Payment Surges - Reuters</title>
                <link>https://news.google.com/rss/articles/CBMi...</link>
                <pubDate>{recent_date_str}</pubDate>
                <source url="https://www.reuters.com">Reuters</source>
            </item>
        </channel></rss>""".encode("utf-8")

        items = parse_rss_xml(xml_content, "Google News (Cambodia)", now_utc)
        self.assertEqual(len(items), 1)
        # Identifies actual publisher and aggregator
        self.assertIn("Reuters", items[0].publisher)
        self.assertIn("Google News", items[0].publisher)
        # Cleans "- Reuters" from title
        self.assertEqual(items[0].title, "Cambodia Digital Payment Surges")

    # 3. Oversized HTTP responses streaming cap
    async def test_oversized_http_responses_stream_cap(self):
        # Create an async mock client that yields large chunks
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Create generator yielding chunks exceeding MAX_FEED_BYTES
        async def fake_aiter():
            for _ in range(10):
                yield b"A" * 50000  # Total 500KB > 350KB

        mock_response.aiter_bytes = fake_aiter

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_ctx

        now_utc = datetime.now(timezone.utc)
        feed_cfg = {"publisher": "BigFeed", "url": "https://example.com/big.xml"}

        # fetch_single_feed caps reading at MAX_FEED_BYTES
        with patch("trend_sources.parse_rss_xml", return_value=[]) as mock_parse:
            await fetch_single_feed(feed_cfg, mock_client, now_utc)
            self.assertTrue(mock_parse.called)
            received_bytes = mock_parse.call_args[0][0]
            self.assertLessEqual(len(received_bytes), MAX_FEED_BYTES)

    # 4. Freshness revalidation of cached feeds
    async def test_freshness_revalidation_of_cached_feeds(self):
        now_utc = datetime.now(timezone.utc)
        # Store an item that was published 50 hours ago (no longer fresh)
        stale_item = NewsItem(
            id=1,
            title="Old Story",
            publisher="News",
            url="http://old.com",
            published_at=now_utc - timedelta(hours=50),
            is_recent=False
        )
        trend_sources._FEED_CACHE["general"] = (now_utc - timedelta(minutes=5), [stale_item])

        # When get_fresh_news_sources is called, it revalidates freshness against now_utc
        with patch("trend_sources.fetch_single_feed", new_callable=AsyncMock, return_value=[]):
            res = await get_fresh_news_sources("general")
            # Stale item is not returned as fresh
            self.assertEqual(len(res), 0)

    # 5. Mixed valid/invalid source IDs [1] and [99] -> MUST reject sourced claims
    async def test_mixed_valid_invalid_source_ids_rejected(self):
        service = AIService()
        fake_items = [
            NewsItem(id=1, title="Valid Tech News", publisher="TechAsia", url="https://example.com/tech", published_at=datetime.now(timezone.utc), is_recent=True)
        ]
        # AI returns both valid [1] and hallucinated [99]
        mixed_ai_response = (
            "🔥 **គំនិតទី ១៖ បច្ចេកវិទ្យាថ្មី**\n"
            "• Hook: មើលបច្ចេកវិទ្យានេះ\n"
            "• What: ព័ត៌មាន AI\n"
            "• ប្រភព៖ [1] និង [99]\n"
        )

        with patch("ai_service.get_fresh_news_sources", return_value=fake_items):
            with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = mixed_ai_response
                result = await service.generate_daily_ideas("ទូទៅ")

                # Sourced claims rejected
                self.assertIn("ការផ្ទៀងផ្ទាត់ប្រភពព័ត៌មានមិនត្រឹមត្រូវ", result)
                # Sourced output NOT cached in daily cache
                self.assertEqual(len(ai_service._DAILY_IDEAS_CACHE), 0)
                # Shows retrieved news list
                self.assertIn("Valid Tech News", result)
                self.assertIn("https://example.com/tech", result)

    # 6. Missing references for one of several ideas -> MUST reject sourced claims
    async def test_missing_references_for_one_of_several_ideas(self):
        service = AIService()
        fake_items = [
            NewsItem(id=1, title="Valid News", publisher="News", url="https://example.com/1", published_at=datetime.now(timezone.utc), is_recent=True)
        ]
        # Idea 1 has [1], Idea 2 has NO source citation
        incomplete_citation_response = (
            "🔥 **គំនិតទី ១៖ ប្រធានបទទីមួយ**\n"
            "• Hook: Hook 1\n"
            "• ប្រភព៖ [1]\n\n"
            "🔥 **គំនិតទី ២៖ ប្រធានបទទីពីរ**\n"
            "• Hook: Hook 2 គ្មានប្រភព\n"
            "• What: ខ្លឹមសារ\n"
        )

        with patch("ai_service.get_fresh_news_sources", return_value=fake_items):
            with patch.object(service, "generate_response", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = incomplete_citation_response
                result = await service.generate_daily_ideas("ទូទៅ")

                self.assertIn("ការផ្ទៀងផ្ទាត់ប្រភពព័ត៌មានមិនត្រឹមត្រូវ", result)
                self.assertIn("ខ្វះការយោងប្រភព", result)
                self.assertIn("Valid News", result)

    # 7. No automatic second AI call on citation failure
    async def test_no_automatic_second_ai_call_on_citation_failure(self):
        service = AIService()
        fake_items = [
            NewsItem(id=1, title="Sample News", publisher="News", url="https://example.com/1", published_at=datetime.now(timezone.utc), is_recent=True)
        ]
        # AI returns output with no valid references
        no_ref_response = "🔥 **គំនិតទី ១**\n• Hook: Test\n• គ្មានប្រភពសោះ"

        mock_gen = AsyncMock(return_value=no_ref_response)
        with patch("ai_service.get_fresh_news_sources", return_value=fake_items):
            with patch.object(service, "generate_response", mock_gen):
                result = await service.generate_daily_ideas("ទូទៅ")
                # Exactly ONE Gemini call was made - NO automatic second call!
                self.assertEqual(mock_gen.call_count, 1)
                self.assertIn("ការផ្ទៀងផ្ទាត់ប្រភពព័ត៌មានមិនត្រឹមត្រូវ", result)

    # 8. Valid citations build links ONLY in Python from retrieved records
    async def test_valid_citations_build_python_links(self):
        service = AIService()
        fake_items = [
            NewsItem(id=1, title="Cambodia Fintech Growth", publisher="KhmerBiz", url="https://example.com/fintech", published_at=datetime.now(timezone.utc), is_recent=True)
        ]
        valid_response = (
            "🔥 **គំនិតទី ១៖ ការទូទាត់ឌីជីថល**\n"
            "• Hook: តើអ្នកដឹងទេ?\n"
            "• What: ការទូទាត់កើនឡើង\n"
            "• ប្រភព៖ [1]\n"
        )
        with patch("ai_service.get_fresh_news_sources", return_value=fake_items):
            with patch.object(service, "generate_response", new_callable=AsyncMock, return_value=valid_response):
                result = await service.generate_daily_ideas("ទូទៅ")
                self.assertIn("គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ", result)
                self.assertIn("[KhmerBiz: Cambodia Fintech Growth](https://example.com/fintech)", result)
                self.assertIn("ប្រភពព័ត៌មានយោងពិតប្រាកដ", result)
                self.assertIn("មិនមែនជាទិន្នន័យ Trend ផ្ទាល់ពី TikTok/Facebook", result)

    # 9. Narrow category with no evidence -> honest fallback without attaching unrelated news
    async def test_narrow_category_no_evidence_honest_fallback(self):
        service = AIService()
        # Tech category returns empty list from trend_sources
        with patch("ai_service.get_fresh_news_sources", return_value=[]):
            with patch.object(service, "generate_response", new_callable=AsyncMock, return_value="គំនិតទូទៅពី AI") as mock_gen:
                result = await service.generate_daily_ideas("tech")
                self.assertIn("គំនិតមាតិកាទូទៅពី AI", result)
                self.assertIn("មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ", result)
                # Unrelated general news was NOT attached
                self.assertNotIn("ប្រភពព័ត៌មានយោងពិតប្រាកដ", result)

    # 10. One generation for multiple broadcast subscribers
    async def test_broadcast_generates_once_for_all(self):
        bot.subscribers = {1, 2, 3, 4, 5}
        mock_bot = AsyncMock()
        mock_ctx = MagicMock()
        mock_ctx.bot = mock_bot

        with patch("bot.ai_service.generate_daily_ideas", new_callable=AsyncMock, return_value="គំនិតផ្សាយប្រចាំថ្ងៃ") as mock_gen:
            await send_daily_content(mock_ctx)
            mock_gen.assert_called_once_with("ទូទៅ")
            self.assertEqual(mock_bot.send_message.call_count, 5)

if __name__ == "__main__":
    unittest.main()
