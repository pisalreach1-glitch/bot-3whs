"""
app/navigation.py - Screen transitions, navigation history, and Back/Home routing.

Tracks current screen, screen history stack, draft ID, and selected script pointer per UserKey.
"""

from typing import Dict, List, Optional, Tuple
from app.models import UserKey, NavigationState

class Screens:
    HOME = "HOME"
    FORMAT_SELECTION = "FORMAT_SELECTION"
    TOPIC_INPUT = "TOPIC_INPUT"
    DRAFT_REVIEW = "DRAFT_REVIEW"
    DRAFT_DURATION = "DRAFT_DURATION"
    IDEA_CATEGORY = "IDEA_CATEGORY"
    IDEA_RESULTS = "IDEA_RESULTS"
    COMEDY_STYLE = "COMEDY_STYLE"
    COMEDY_ACTORS = "COMEDY_ACTORS"
    SCRIPT_SUMMARY = "SCRIPT_SUMMARY"
    SCRIPT_READ = "SCRIPT_READ"
    SCRIPT_SHOTS = "SCRIPT_SHOTS"
    SCRIPT_CAPTION = "SCRIPT_CAPTION"
    HOOK_OPTIONS = "HOOK_OPTIONS"
    SETTINGS = "SETTINGS"
    DEFAULT_DURATION = "DEFAULT_DURATION"
    PACE_SAMPLE = "PACE_SAMPLE"
    PACE_SECONDS = "PACE_SECONDS"
    HELP = "HELP"

class NavigationManager:
    def __init__(self):
        self._states: Dict[UserKey, NavigationState] = {}

    def get_state(self, user_key: UserKey) -> NavigationState:
        if user_key not in self._states:
            self._states[user_key] = NavigationState(
                current_screen=Screens.HOME,
                screen_history=[],
                draft_id=None,
                selected_script_id=None,
                selected_script_version=None,
            )
        return self._states[user_key]

    def go_to(
        self,
        user_key: UserKey,
        screen: str,
        draft_id: Optional[str] = None,
        script_id: Optional[str] = None,
        script_version: Optional[int] = None,
    ) -> NavigationState:
        state = self.get_state(user_key)
        if state.current_screen != screen:
            state.screen_history.append(state.current_screen)
            # Limit history depth to 20 to avoid memory growth
            if len(state.screen_history) > 20:
                state.screen_history.pop(0)

        state.current_screen = screen
        if draft_id is not None:
            state.draft_id = draft_id
        if script_id is not None:
            state.selected_script_id = script_id
        if script_version is not None:
            state.selected_script_version = script_version
        return state

    def go_back(self, user_key: UserKey) -> Tuple[str, NavigationState]:
        """Pops previous screen from history. If history is empty, returns to HOME."""
        state = self.get_state(user_key)
        if state.screen_history:
            prev_screen = state.screen_history.pop()
            state.current_screen = prev_screen
        else:
            state.current_screen = Screens.HOME
        return state.current_screen, state

    def go_home(self, user_key: UserKey) -> NavigationState:
        """Resets navigation to HOME, clearing history while preserving draft/script pointers."""
        state = self.get_state(user_key)
        state.current_screen = Screens.HOME
        state.screen_history.clear()
        return state

    def set_draft(self, user_key: UserKey, draft_id: str):
        state = self.get_state(user_key)
        state.draft_id = draft_id

    def set_script(self, user_key: UserKey, script_id: str, version: int):
        state = self.get_state(user_key)
        state.selected_script_id = script_id
        state.selected_script_version = version

    def clear(self):
        """Clears all in-memory navigation states."""
        self._states.clear()

navigation = NavigationManager()
