"""
config.py - Environment and validated configuration for 3WHs Bot.

Validates environment variables, provides defaults, and prevents secret leakage in logs.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    gemini_api_key: str
    port: Optional[int]
    daily_time: str
    timezone: str
    db_path: str
    default_duration: str
    default_pace: float

    def validate(self) -> None:
        """Validates critical configuration. Does not raise for missing token in test mode."""
        if not self.timezone:
            raise ValueError("TIMEZONE must not be empty.")
        if not self.db_path:
            raise ValueError("BOT_DB_PATH must not be empty.")

    def __repr__(self) -> str:
        token_masked = "***" if self.telegram_bot_token else "NOT_SET"
        key_masked = "***" if self.gemini_api_key else "NOT_SET"
        return (
            f"AppConfig(token={token_masked}, key={key_masked}, port={self.port}, "
            f"daily_time='{self.daily_time}', timezone='{self.timezone}', db_path='{self.db_path}')"
        )

def load_config() -> AppConfig:
    port_val = None
    port_str = os.getenv("PORT", "").strip()
    if port_str:
        try:
            port_val = int(port_str)
        except ValueError:
            pass

    cfg = AppConfig(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        port=port_val,
        daily_time=os.getenv("DAILY_TIME", "08:00").strip(),
        timezone=os.getenv("TIMEZONE", "Asia/Phnom_Penh").strip(),
        db_path=os.getenv("BOT_DB_PATH", "bot_database.sqlite3").strip(),
        default_duration=os.getenv("DEFAULT_DURATION", "60 វិនាទី").strip(),
        default_pace=float(os.getenv("DEFAULT_PACE", "10.0")),
    )
    cfg.validate()
    return cfg
