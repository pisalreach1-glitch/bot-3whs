import os
import logging
from dotenv import load_dotenv
from prompts import (
    SYSTEM_INSTRUCTION,
    get_script_generation_prompt,
    get_pov_story_prompt,
    get_myth_reality_prompt,
    get_before_after_prompt,
    get_hot_take_prompt,
    get_top_list_prompt,
    get_daily_ideas_prompt,
    get_chat_prompt,
)

load_dotenv()
logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.client = None
        self.sdk_type = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set.")
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.sdk_type = "google-genai"
            logger.info("Initialized Gemini with google-genai SDK.")
            return
        except ImportError:
            pass

        try:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=self.api_key)
            self.client = genai_legacy.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=SYSTEM_INSTRUCTION
            )
            self.sdk_type = "google-generativeai"
            logger.info("Initialized Gemini with google-generativeai SDK.")
            return
        except ImportError:
            pass

        logger.error("No Gemini SDK found. Please install google-genai or google-generativeai.")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    async def generate_response(self, prompt: str) -> str:
        """Generate response from Gemini AI with automatic fallback models."""
        if not self.is_configured():
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
            self._init_client()
            if not self.is_configured():
                return "⚠️ សូមបញ្ចូល `GEMINI_API_KEY` នៅក្នុង file `.env` ជាមុនសិន!"

        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]

        last_error = None
        for model_name in models_to_try:
            try:
                if self.sdk_type == "google-genai":
                    from google.genai import types
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=0.75,
                        )
                    )
                    if response and response.text:
                        return response.text
                elif self.sdk_type == "google-generativeai":
                    import google.generativeai as genai_legacy
                    model = genai_legacy.GenerativeModel(
                        model_name=model_name,
                        system_instruction=SYSTEM_INSTRUCTION
                    )
                    response = model.generate_content(prompt)
                    if response and response.text:
                        return response.text
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}. Trying fallback...")
                last_error = e
                continue

        return (
            f"❌ **AI ស្ថានភាពមមាញឹក (High Demand)**\n\n"
            f"Error: {str(last_error)}\n\n"
            "🔄 _សូមសាកល្បងម្ដងទៀតក្នុងរយៈពេល ១-២ នាទី!_"
        )

    # ─────────────────────────────────────────────
    # Content Type Methods
    # ─────────────────────────────────────────────

    async def generate_script(self, topic: str, duration: str = "60 វិនាទី") -> str:
        """3WHs Hook Script"""
        prompt = get_script_generation_prompt(topic, duration)
        return await self.generate_response(prompt)

    async def generate_pov_story(self, situation: str, niche: str, duration: str = "60 វិនាទី") -> str:
        """POV / Storytelling Content"""
        prompt = get_pov_story_prompt(situation, niche, duration)
        return await self.generate_response(prompt)

    async def generate_myth_reality(self, myth: str, niche: str, duration: str = "60 វិនាទី") -> str:
        """Myth vs Reality Content"""
        prompt = get_myth_reality_prompt(myth, niche, duration)
        return await self.generate_response(prompt)

    async def generate_before_after(self, transformation: str, niche: str, duration: str = "60 វិនាទី") -> str:
        """Before & After / Transformation Content"""
        prompt = get_before_after_prompt(transformation, niche, duration)
        return await self.generate_response(prompt)

    async def generate_hot_take(self, opinion: str, niche: str, duration: str = "60 វិនាទី") -> str:
        """Hot Take / Opinion Content"""
        prompt = get_hot_take_prompt(opinion, niche, duration)
        return await self.generate_response(prompt)

    async def generate_top_list(self, topic: str, niche: str, duration: str = "60 វិនាទី") -> str:
        """Top List / Ranking Content"""
        prompt = get_top_list_prompt(topic, niche, duration)
        return await self.generate_response(prompt)

    async def generate_content_by_type(
        self,
        content_type: str,
        topic: str,
        niche: str,
        duration: str = "60 វិនាទី"
    ) -> str:
        """Route to correct generator based on content_type."""
        if content_type == "3whs":
            return await self.generate_script(topic, duration)
        elif content_type == "pov":
            return await self.generate_pov_story(topic, niche, duration)
        elif content_type == "myth":
            return await self.generate_myth_reality(topic, niche, duration)
        elif content_type == "transform":
            return await self.generate_before_after(topic, niche, duration)
        elif content_type == "hottake":
            return await self.generate_hot_take(topic, niche, duration)
        elif content_type == "toplist":
            return await self.generate_top_list(topic, niche, duration)
        else:
            return await self.generate_script(topic, duration)

    async def generate_daily_ideas(self, category: str = "General") -> str:
        """Daily content ideas"""
        prompt = get_daily_ideas_prompt(category)
        return await self.generate_response(prompt)

    async def chat(self, user_message: str) -> str:
        """Free-text chat"""
        prompt = get_chat_prompt(user_message)
        return await self.generate_response(prompt)
