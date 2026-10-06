import os
import logging
from prompts import (
    SYSTEM_INSTRUCTION,
    get_script_generation_prompt,
    get_daily_ideas_prompt,
    get_chat_prompt,
)

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.client = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set.")
            return

        try:
            # First try google-genai (v1 SDK)
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.sdk_type = "google-genai"
            logger.info("Initialized Gemini with google-genai SDK.")
            return
        except ImportError:
            pass

        try:
            # Fallback to google-generativeai
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
        """Generate response from Gemini AI with automatic fallback models on high demand."""
        if not self.is_configured():
            # Refresh if api_key was added later
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
            self._init_client()
            if not self.is_configured():
                return "⚠️ សូមបញ្ចូល `GEMINI_API_KEY` នៅក្នុង file `.env` ជាមុនសិន!"

        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-1.5-flash-latest",
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
                            temperature=0.7,
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
                err_msg = str(e)
                logger.warning(f"Model {model_name} failed with error: {err_msg}. Trying next fallback model...")
                last_error = e
                continue

        logger.exception("All Gemini fallback models failed:")
        return f"❌ មានបញ្ហាក្នុងការទាក់ទងទៅកាន់ AI (Server Busy/High Demand): {str(last_error)}\n\nសូមសាកល្បងចុចម្តងទៀតក្នុងរយៈពេលបន្តិចទៀតនេះ។"

    async def generate_script(self, topic: str, duration: str = "60s") -> str:
        prompt = get_script_generation_prompt(topic, duration)
        return await self.generate_response(prompt)

    async def generate_daily_ideas(self, category: str = "General / Business / Tech / Self-improvement") -> str:
        prompt = get_daily_ideas_prompt(category)
        return await self.generate_response(prompt)

    async def chat(self, user_message: str) -> str:
        prompt = get_chat_prompt(user_message)
        return await self.generate_response(prompt)
