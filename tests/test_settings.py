"""
tests/test_settings.py - Tests for Settings handlers: Duration setting, Pace calibration, and Subscription.
"""

import tempfile
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import UserKey
from app.storage import Storage
from app.navigation import navigation, Screens
from app.handlers.settings import handle_settings_callback, handle_pace_seconds_input
from app.handlers.commands import pace_command, subscribe_command, unsubscribe_command

class TestSettingsFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_settings.sqlite3"
        self.storage = Storage(db_path=self.db_path)
        self.user = UserKey(chat_id=888, user_id=999)

    def tearDown(self):
        self.temp_dir.cleanup()

    async def _async_test_default_duration_change(self):
        # 1. Initial default duration
        s = self.storage.get_settings(self.user)
        self.assertEqual(s["duration"], "60 វិនាទី")

        # 2. Simulate clicking duration button: set:dur:180 វិនាទី
        mock_query = AsyncMock()
        mock_query.data = "set:dur:180 វិនាទី"
        mock_update = MagicMock()
        mock_update.callback_query = mock_query

        mock_context = MagicMock()
        mock_context.bot_data = {"storage": self.storage}

        with patch("app.handlers.settings.get_user_key", return_value=self.user):
            await handle_settings_callback(mock_update, mock_context)

        # 3. Verify duration updated in SQLite
        updated = self.storage.get_settings(self.user)
        self.assertEqual(updated["duration"], "180 វិនាទី")
        mock_query.edit_message_text.assert_called_once()

    def test_default_duration_change(self):
        asyncio.run(self._async_test_default_duration_change())

    async def _async_test_pace_calibration_input(self):
        navigation.go_to(self.user, Screens.PACE_SECONDS)
        mock_update = MagicMock()
        mock_msg = AsyncMock()
        mock_update.message = mock_msg

        mock_context = MagicMock()
        mock_context.bot_data = {"storage": self.storage}

        # 1. Enter valid reading seconds e.g. "15.0"
        with patch("app.handlers.settings.get_user_key", return_value=self.user):
            await handle_pace_seconds_input(mock_update, mock_context, "15.0")

        settings = self.storage.get_settings(self.user)
        self.assertGreater(settings["pace"], 0)
        self.assertNotEqual(settings["pace"], 10.0)
        self.assertIn("បានកំណត់ល្បឿននិយាយផ្ទាល់ខ្លួនជោគជ័យ", mock_msg.reply_text.call_args[0][0])

        # 2. Reject non-number input
        mock_msg.reset_mock()
        with patch("app.handlers.settings.get_user_key", return_value=self.user):
            await handle_pace_seconds_input(mock_update, mock_context, "abc")
        self.assertIn("លេខវិនាទីសុទ្ធ", mock_msg.reply_text.call_args[0][0])

        # 3. Reject negative / out of range seconds
        mock_msg.reset_mock()
        with patch("app.handlers.settings.get_user_key", return_value=self.user):
            await handle_pace_seconds_input(mock_update, mock_context, "1.0")
        self.assertIn("ចន្លោះពី 2 ដល់ 300", mock_msg.reply_text.call_args[0][0])

    def test_pace_calibration_input(self):
        asyncio.run(self._async_test_pace_calibration_input())

    async def _async_test_subscription_toggle(self):
        self.assertFalse(self.storage.is_subscribed(self.user))

        mock_query = AsyncMock()
        mock_query.data = "set:sub_toggle"
        mock_update = MagicMock()
        mock_update.callback_query = mock_query

        mock_context = MagicMock()
        mock_context.bot_data = {"storage": self.storage}

        with patch("app.handlers.settings.get_user_key", return_value=self.user):
            # Toggle ON
            await handle_settings_callback(mock_update, mock_context)
            self.assertTrue(self.storage.is_subscribed(self.user))

            # Toggle OFF
            await handle_settings_callback(mock_update, mock_context)
            self.assertFalse(self.storage.is_subscribed(self.user))

    def test_subscription_toggle(self):
        asyncio.run(self._async_test_subscription_toggle())

    async def _async_test_slash_pace_and_subscribe_commands(self):
        mock_update = MagicMock()
        mock_msg = AsyncMock()
        mock_update.message = mock_msg

        mock_context = MagicMock()
        mock_context.bot_data = {"storage": self.storage}

        # 1. /subscribe command
        with patch("app.handlers.commands.get_user_key", return_value=self.user):
            await subscribe_command(mock_update, mock_context)
            self.assertTrue(self.storage.is_subscribed(self.user))

        # 2. /unsubscribe command
        with patch("app.handlers.commands.get_user_key", return_value=self.user):
            await unsubscribe_command(mock_update, mock_context)
            self.assertFalse(self.storage.is_subscribed(self.user))

        # 3. /pace <sec> <sample> command
        mock_context.args = ["10.0", "អក្សរខ្មែរសម្រាប់ធ្វើតេស្តល្បឿនអាន"]
        with patch("app.handlers.commands.get_user_key", return_value=self.user):
            await pace_command(mock_update, mock_context)
            s = self.storage.get_settings(self.user)
            self.assertGreater(s["pace"], 0)

    def test_slash_pace_and_subscribe_commands(self):
        asyncio.run(self._async_test_slash_pace_and_subscribe_commands())

if __name__ == "__main__":
    unittest.main()
