"""
tests/test_ideas_flow.py - Tests for Ideas flow, source evidence parsing, citation verification, and selection to draft.
"""

import tempfile
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.models import UserKey, Idea, EvidenceRecord, Draft
from app.storage import Storage
from app.services.ideas import parse_generated_ideas, get_or_generate_ideas
from app.handlers.ideas import handle_idea_pick_callback
from app.keyboards import get_ideas_keyboard

class TestIdeasFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_ideas.sqlite3"
        self.storage = Storage(db_path=self.db_path)
        self.user = UserKey(chat_id=555, user_id=777)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_generated_ideas(self):
        raw_text = """
🔥 **គំនិតទី 1: វិធីគ្រប់គ្រងហិរញ្ញវត្ថុឆ្លាតវៃ**
🎯 **Hook**: តើអ្នកដឹងទេថាហេតុអ្វីមនុស្ស ៩០% គ្មានប្រាក់សន្សំ?
⚡ **ទម្រង់**: POV និទានរឿង
📌 **ខ្លឹមសារ**: យោងតាមរបាយការណ៍ [1] ពីធនាគារជាតិ...

🔥 **គំនិតទី 2: អាថ៌កំបាំងសុខភាព**
🎯 **Hook**: ឈប់ញ៉ាំអាហារទាំងនេះភ្លាម!
⚡ **ទម្រង់**: Myth vs Reality
📌 **ខ្លឹមសារ**: ការស្រាវជ្រាវថ្មី [2] បង្ហាញថា...
"""
        ideas = parse_generated_ideas(raw_text)
        self.assertEqual(len(ideas), 2)

        self.assertEqual(ideas[0].id, 1)
        self.assertIn("វិធីគ្រប់គ្រងហិរញ្ញវត្ថុឆ្លាតវៃ", ideas[0].topic)
        self.assertIn("តើអ្នកដឹងទេថាហេតុអ្វីមនុស្ស ៩០% គ្មានប្រាក់សន្សំ?", ideas[0].hook)
        self.assertEqual(ideas[0].suggested_format, "pov")
        self.assertEqual(ideas[0].source_ids, [1])

        self.assertEqual(ideas[1].id, 2)
        self.assertIn("អាថ៌កំបាំងសុខភាព", ideas[1].topic)
        self.assertEqual(ideas[1].suggested_format, "myth")
        self.assertEqual(ideas[1].source_ids, [2])

    async def _async_test_citation_verification_rejects_invalid_source_id(self):
        ai_mock = MagicMock()
        ai_mock._is_error_response = MagicMock(return_value=False)

        # AI hallucinated [99] which is not in evidence (only 1 exists)
        ai_mock.generate_response = AsyncMock(return_value="""
🔥 **គំនិតទី 1: ប្រធានបទ**
🎯 **Hook**: Hook text
📌 **ខ្លឹមសារ**: យោង [99] ព័ត៌មាន...
""")

        mock_news = [
            MagicMock(id=1, title="News 1", publisher="Post", url="http://example.com/1", published_at=datetime.now(timezone.utc))
        ]

        with patch("app.services.ideas.get_fresh_news_sources", new_callable=AsyncMock, return_value=mock_news):
            batch_tok, ideas, ev, fail_msg = await get_or_generate_ideas(
                user_key=self.user,
                category="ទូទៅ",
                storage=self.storage,
                ai=ai_mock,
            )
            # Must reject whole batch on invalid reference
            self.assertIsNone(batch_tok)
            self.assertEqual(len(ideas), 0)
            self.assertIsNotNone(fail_msg)
            self.assertIn("99", fail_msg)
            # Does not spend second AI call
            self.assertEqual(ai_mock.generate_response.call_count, 1)

    def test_citation_verification_rejects_invalid_source_id(self):
        asyncio.run(self._async_test_citation_verification_rejects_invalid_source_id())

    async def _async_test_idea_pick_creates_draft_with_evidence(self):
        # 1. Store an idea batch in SQLite
        evidence = [
            EvidenceRecord(
                id="1",
                url="http://news.com/1",
                platform_or_feed="rss",
                publisher="Kampuchea Thmey",
                retrieved_at=datetime.now(timezone.utc),
                title="Economic Growth in Cambodia",
            )
        ]
        ideas = [
            Idea(
                id=1,
                topic="Economic Growth Strategies",
                hook="Why Cambodia's economy is booming?",
                suggested_format="toplist",
                source_ids=[1],
                evidence_status="verified",
            )
        ]
        batch_token = "batch_test1"
        self.storage.save_idea_batch(batch_token, self.user, "ទូទៅ", ideas, evidence)

        # 2. Simulate picking Idea #1
        mock_update = MagicMock()
        mock_update.effective_chat.id = 555
        mock_update.effective_user.id = 777
        mock_query = AsyncMock()
        mock_query.data = f"i:{batch_token}:1"
        mock_msg = AsyncMock()
        mock_query.message = mock_msg
        mock_update.callback_query = mock_query

        mock_context = MagicMock()
        mock_context.bot_data = {
            "storage": self.storage,
            "ai": MagicMock(),
            "task_mgr": MagicMock(),
        }

        with patch("app.handlers.ideas.get_user_key", return_value=self.user):
            await handle_idea_pick_callback(mock_update, mock_context)

        # 3. Verify draft was created and stored in SQLite
        from app.navigation import navigation, Screens
        nav_state = navigation.get_state(self.user)
        self.assertEqual(nav_state.current_screen, Screens.DRAFT_REVIEW)
        self.assertIsNotNone(nav_state.draft_id)

        draft = self.storage.get_draft(nav_state.draft_id)
        self.assertIsNotNone(draft)
        self.assertEqual(draft.topic, "Economic Growth Strategies")
        self.assertEqual(draft.format_id, "toplist")
        self.assertEqual(draft.evidence_ids, ["1"])

    def test_idea_pick_creates_draft_with_evidence(self):
        asyncio.run(self._async_test_idea_pick_creates_draft_with_evidence())

    def test_keyboard_never_attaches_script_refinements_to_ideas(self):
        """Ideas keyboard must only provide idea selections, Back, and Home."""
        kb = get_ideas_keyboard("batch_123", 3)
        flattened_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        for cb in flattened_callbacks:
            self.assertFalse(cb.startswith("s:"), f"Ideas keyboard contained script action callback: {cb}")
            self.assertFalse("shorten" in cb)
            self.assertFalse("hooks" in cb)
            self.assertFalse("regen" in cb)

if __name__ == "__main__":
    unittest.main()
