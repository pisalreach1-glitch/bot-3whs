"""
app/task_manager.py - Per-User Request Tracking, Deduplication, and Coordinated Cancellation.

Prevents duplicate concurrent requests per UserKey, stops stale/cancelled results
from being sent or saved, and ensures old finally blocks do not clear newer state.
"""

import asyncio
import logging
from typing import Dict, Optional, Set, Tuple
from app.models import UserKey

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self):
        self._tokens: Dict[UserKey, int] = {}
        self._active_tasks: Dict[UserKey, asyncio.Task] = {}
        self._active_requests: Dict[UserKey, str] = {}
        self._cancelled_tokens: Set[Tuple[UserKey, int]] = set()
        self._lock = asyncio.Lock()

    async def start_request(self, user_key: UserKey, request_id: str) -> Optional[int]:
        """
        Attempts to acquire request lock for user.
        Returns integer token if successfully started, or None if a request is already running.
        """
        async with self._lock:
            existing_task = self._active_tasks.get(user_key)
            if existing_task and not existing_task.done():
                logger.warning(f"Duplicate request blocked for {user_key.key_str}")
                return None

            token = self._tokens.get(user_key, 0) + 1
            self._tokens[user_key] = token
            self._active_tasks[user_key] = asyncio.current_task()
            self._active_requests[user_key] = request_id
            return token

    def get_active_request(self, user_key: UserKey) -> Optional[str]:
        """Returns current active request_id for user if one is in-flight."""
        task = self._active_tasks.get(user_key)
        if task and not task.done():
            return self._active_requests.get(user_key)
        return None

    async def cancel_request(self, user_key: UserKey) -> bool:
        """
        Cancels any active task for user, increments token to invalidate in-flight results,
        and clears active state.
        """
        async with self._lock:
            task = self._active_tasks.get(user_key)
            was_active = False
            cur_token = self._tokens.get(user_key, 0)

            if task and not task.done():
                if task != asyncio.current_task():
                    task.cancel()
                was_active = True

            # Invalidate current token so late returns cannot save or send
            self._tokens[user_key] = cur_token + 1
            self._active_tasks.pop(user_key, None)
            self._active_requests.pop(user_key, None)
            return was_active

    def is_current_request(self, user_key: UserKey, token: int) -> bool:
        """Checks if token is still current and has not been cancelled."""
        return self._tokens.get(user_key) == token

    async def finish_request(self, user_key: UserKey, token: int):
        """Safely cleans up active task only if current token matches."""
        async with self._lock:
            if self._tokens.get(user_key) == token:
                self._active_tasks.pop(user_key, None)
                self._active_requests.pop(user_key, None)

task_manager = TaskManager()
