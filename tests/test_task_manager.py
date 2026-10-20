"""
tests/test_task_manager.py - Tests for per-user task tracking, deduplication, cancellation, and race protection.
"""

import asyncio
import unittest
from app.models import UserKey
from app.task_manager import TaskManager

class TestTaskManager(unittest.TestCase):
    def setUp(self):
        self.tm = TaskManager()
        self.user1 = UserKey(chat_id=100, user_id=200)
        self.user2 = UserKey(chat_id=100, user_id=300)

    async def _async_test_deduplication(self):
        # User 1 starts a request
        tok1 = await self.tm.start_request(self.user1, "req_1")
        self.assertIsNotNone(tok1)
        self.assertTrue(self.tm.is_current_request(self.user1, tok1))
        self.assertEqual(self.tm.get_active_request(self.user1), "req_1")

        # Second simultaneous request by user 1 is blocked
        tok2 = await self.tm.start_request(self.user1, "req_2")
        self.assertIsNone(tok2, "Concurrent duplicate request for the same user must be blocked")

        # User 2 can start concurrently without interference
        tok_u2 = await self.tm.start_request(self.user2, "req_u2")
        self.assertIsNotNone(tok_u2)

        # Finish User 1 request
        await self.tm.finish_request(self.user1, tok1)

        # Now User 1 can start a new request
        tok3 = await self.tm.start_request(self.user1, "req_3")
        self.assertIsNotNone(tok3)
        self.assertNotEqual(tok1, tok3)
        await self.tm.finish_request(self.user1, tok3)
        await self.tm.finish_request(self.user2, tok_u2)

    def test_deduplication(self):
        asyncio.run(self._async_test_deduplication())

    async def _async_test_cancellation_invalidates_token(self):
        tok1 = await self.tm.start_request(self.user1, "req_1")
        self.assertTrue(self.tm.is_current_request(self.user1, tok1))

        # Cancel request
        was_active = await self.tm.cancel_request(self.user1)
        self.assertTrue(was_active)

        # Token 1 is now STALE / invalid
        self.assertFalse(self.tm.is_current_request(self.user1, tok1))
        self.assertIsNone(self.tm.get_active_request(self.user1))

        # Further cancellation when inactive returns False
        was_active2 = await self.tm.cancel_request(self.user1)
        self.assertFalse(was_active2)

    def test_cancellation_invalidates_token(self):
        asyncio.run(self._async_test_cancellation_invalidates_token())

    async def _async_test_old_finally_cannot_clear_newer_request(self):
        # 1. User starts req_1 (tok 1)
        tok1 = await self.tm.start_request(self.user1, "req_1")

        # 2. User cancels req_1
        await self.tm.cancel_request(self.user1)

        # 3. User starts req_2 (tok 3 because cancel incremented to 2)
        tok2 = await self.tm.start_request(self.user1, "req_2")
        self.assertEqual(self.tm.get_active_request(self.user1), "req_2")

        # 4. Old finally block for tok1 attempts to finish
        await self.tm.finish_request(self.user1, tok1)

        # 5. Req 2 must STILL be active and not cleared by req 1's finally
        self.assertTrue(self.tm.is_current_request(self.user1, tok2))
        self.assertEqual(self.tm.get_active_request(self.user1), "req_2")

        # Cleanup
        await self.tm.finish_request(self.user1, tok2)

    def test_old_finally_cannot_clear_newer_request(self):
        asyncio.run(self._async_test_old_finally_cannot_clear_newer_request())

    async def _async_test_user_isolation(self):
        tok1 = await self.tm.start_request(self.user1, "req_user1")
        tok2 = await self.tm.start_request(self.user2, "req_user2")

        # Cancelling user1 does not affect user2
        await self.tm.cancel_request(self.user1)
        self.assertFalse(self.tm.is_current_request(self.user1, tok1))
        self.assertTrue(self.tm.is_current_request(self.user2, tok2))

        await self.tm.finish_request(self.user2, tok2)

    def test_user_isolation(self):
        asyncio.run(self._async_test_user_isolation())

if __name__ == "__main__":
    unittest.main()
