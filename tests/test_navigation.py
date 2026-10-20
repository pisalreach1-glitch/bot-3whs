"""
tests/test_navigation.py - Tests for screen transitions, Back history stack, and Home state preservation.
"""

import unittest
from app.models import UserKey
from app.navigation import NavigationManager, Screens

class TestNavigation(unittest.TestCase):
    def setUp(self):
        self.nav = NavigationManager()
        self.user1 = UserKey(chat_id=1001, user_id=2001)
        self.user2 = UserKey(chat_id=1001, user_id=2002)  # Same chat, different user

    def test_default_state_is_home(self):
        state = self.nav.get_state(self.user1)
        self.assertEqual(state.current_screen, Screens.HOME)
        self.assertEqual(state.screen_history, [])
        self.assertIsNone(state.draft_id)
        self.assertIsNone(state.selected_script_id)

    def test_screen_transitions_and_history(self):
        self.nav.go_to(self.user1, Screens.FORMAT_SELECTION, draft_id="draft_1")
        state = self.nav.get_state(self.user1)
        self.assertEqual(state.current_screen, Screens.FORMAT_SELECTION)
        self.assertEqual(state.screen_history, [Screens.HOME])
        self.assertEqual(state.draft_id, "draft_1")

        self.nav.go_to(self.user1, Screens.TOPIC_INPUT)
        state = self.nav.get_state(self.user1)
        self.assertEqual(state.current_screen, Screens.TOPIC_INPUT)
        self.assertEqual(state.screen_history, [Screens.HOME, Screens.FORMAT_SELECTION])

        self.nav.go_to(self.user1, Screens.DRAFT_REVIEW)
        state = self.nav.get_state(self.user1)
        self.assertEqual(state.current_screen, Screens.DRAFT_REVIEW)
        self.assertEqual(state.screen_history, [Screens.HOME, Screens.FORMAT_SELECTION, Screens.TOPIC_INPUT])

    def test_go_back_restores_previous_screen(self):
        self.nav.go_to(self.user1, Screens.FORMAT_SELECTION, draft_id="draft_1")
        self.nav.go_to(self.user1, Screens.TOPIC_INPUT)
        self.nav.go_to(self.user1, Screens.DRAFT_REVIEW)

        # Go back to TOPIC_INPUT
        screen, state = self.nav.go_back(self.user1)
        self.assertEqual(screen, Screens.TOPIC_INPUT)
        self.assertEqual(state.current_screen, Screens.TOPIC_INPUT)
        self.assertEqual(state.draft_id, "draft_1")  # Preserves draft_id

        # Go back to FORMAT_SELECTION
        screen, state = self.nav.go_back(self.user1)
        self.assertEqual(screen, Screens.FORMAT_SELECTION)

        # Go back to HOME
        screen, state = self.nav.go_back(self.user1)
        self.assertEqual(screen, Screens.HOME)

        # Empty history stays at HOME
        screen, state = self.nav.go_back(self.user1)
        self.assertEqual(screen, Screens.HOME)

    def test_go_home_clears_history_preserves_pointers(self):
        self.nav.go_to(self.user1, Screens.FORMAT_SELECTION, draft_id="draft_1")
        self.nav.go_to(self.user1, Screens.TOPIC_INPUT)
        self.nav.set_script(self.user1, "script_xyz", 1)

        state = self.nav.go_home(self.user1)
        self.assertEqual(state.current_screen, Screens.HOME)
        self.assertEqual(state.screen_history, [])
        self.assertEqual(state.draft_id, "draft_1")
        self.assertEqual(state.selected_script_id, "script_xyz")
        self.assertEqual(state.selected_script_version, 1)

    def test_user_isolation(self):
        """Users in the same chat have independent navigation state."""
        self.nav.go_to(self.user1, Screens.FORMAT_SELECTION, draft_id="d_user1")
        self.nav.go_to(self.user2, Screens.IDEA_CATEGORY, draft_id="d_user2")

        state1 = self.nav.get_state(self.user1)
        state2 = self.nav.get_state(self.user2)

        self.assertEqual(state1.current_screen, Screens.FORMAT_SELECTION)
        self.assertEqual(state1.draft_id, "d_user1")

        self.assertEqual(state2.current_screen, Screens.IDEA_CATEGORY)
        self.assertEqual(state2.draft_id, "d_user2")

    def test_history_depth_capped(self):
        for i in range(30):
            self.nav.go_to(self.user1, f"SCREEN_{i}")
        state = self.nav.get_state(self.user1)
        self.assertLessEqual(len(state.screen_history), 20)

if __name__ == "__main__":
    unittest.main()
