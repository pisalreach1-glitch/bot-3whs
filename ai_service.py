import os
import re
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pytz
from dotenv import load_dotenv

from trend_sources import get_fresh_news_sources, NewsItem
from script_models import (
    Scene,
    ScriptPlan,
    parse_duration_seconds,
    parse_and_validate_script_plan,
    format_script_for_telegram,
    DEFAULT_CHARS_PER_SECOND,
)
from prompts import (
    SYSTEM_INSTRUCTION,
    get_script_generation_prompt,
    get_pov_story_prompt,
    get_myth_reality_prompt,
    get_before_after_prompt,
    get_hot_take_prompt,
    get_top_list_prompt,
    get_refine_hook_prompt,
    get_refine_shorten_prompt,
    get_news_grounded_ideas_prompt,
    get_daily_ideas_prompt,
    get_chat_prompt,
)

load_dotenv()
logger = logging.getLogger(__name__)

# In-memory daily ideas cache: "YYYY-MM-DD_category" -> cached_text
_DAILY_IDEAS_CACHE: Dict[str, str] = {}
_IDEAS_LOCK = asyncio.Lock()
REQUEST_TIMEOUT_SECONDS = 45.0

def clear_daily_ideas_cache():
    """Clear cached daily ideas (useful for testing)."""
    _DAILY_IDEAS_CACHE.clear()

class AIService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.client = None
        self.sdk_type = None
        self.last_api_status = "មិនទាន់បានតេស្ត"
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

    def get_status_info(self) -> dict:
        return {
            "configured": self.is_configured(),
            "sdk": self.sdk_type or "មិនទាន់ភ្ជាប់",
            "last_status": getattr(self, "last_api_status", "ធម្មតា"),
        }

    def _generate_sync(self, prompt: str, is_json: bool = False) -> str:
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]

        errors = []
        for model_name in models_to_try:
            try:
                if self.sdk_type == "google-genai":
                    from google.genai import types
                    config_kwargs = {
                        "system_instruction": SYSTEM_INSTRUCTION,
                        "temperature": 0.7,
                    }
                    if is_json:
                        config_kwargs["response_mime_type"] = "application/json"
                    
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(**config_kwargs)
                    )
                    if response and response.text:
                        self.last_api_status = "🟢 ដំណើរការល្អ (Online)"
                        return response.text
                elif self.sdk_type == "google-generativeai":
                    import google.generativeai as genai_legacy
                    gen_config = {}
                    if is_json:
                        gen_config["response_mime_type"] = "application/json"
                    model = genai_legacy.GenerativeModel(
                        model_name=model_name,
                        system_instruction=SYSTEM_INSTRUCTION,
                        generation_config=gen_config if gen_config else None
                    )
                    response = model.generate_content(prompt)
                    if response and response.text:
                        self.last_api_status = "🟢 ដំណើរការល្អ (Online)"
                        return response.text
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Model {model_name} failed: {err_str}")
                errors.append(f"{model_name}: {err_str}")
                continue

        # Check if any errors were quota related
        all_err_str = " ".join(errors).lower()
        if "429" in all_err_str or "quota" in all_err_str or "exhausted" in all_err_str:
            self.last_api_status = "⚠️ Quota Limit"
            return (
                "⚠️ **ប្រព័ន្ធ AI ទទួលសំណើច្រើន ឬដល់កម្រិតកំណត់បណ្ដោះអាសន្ន (Quota Limit)**\n\n"
                "Google Gemini Free Tier កំពុងរង់ចាំ Reset សំណើបន្តិច។\n"
                "👉 សូមរង់ចាំមួយស្របក់ រួចចុចប៊ូតុង **[🔁 បង្កើតម្ដងទៀត]** នោះវានឹងដំណើរការវិញជាធម្មតា!"
            )

        self.last_api_status = f"🔴 Error: {errors[-1][:50] if errors else 'Unknown'}"
        return (
            f"❌ **AI មិនទាន់អាចឆ្លើយតបបាននៅពេលនេះ**\n\n"
            f"មូលហេតុ: {errors[-1] if errors else 'High Demand'}\n\n"
            "🔄 _សូមចុចប៊ូតុង [🔁 បង្កើតម្ដងទៀត] ក្នុងរយៈពេលខ្លីខាងមុខ!_"
        )

    async def generate_response(self, prompt: str, is_json: bool = False) -> str:
        """
        Generate response asynchronously in a separate thread with a timeout 
        so it does not block the Telegram event loop.
        """
        if not self.is_configured():
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
            self._init_client()
            if not self.is_configured():
                self.last_api_status = "🔴 ខ្វះ API Key"
                return "⚠️ សូមបញ្ចូល `GEMINI_API_KEY` នៅក្នុង file `.env` ជាមុនសិន!"

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._generate_sync, prompt, is_json),
                timeout=REQUEST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            self.last_api_status = "⚠️ Request Timeout"
            return "⚠️ **សំណើចំណាយពេលយូរពេក (Request Timeout)**\nសូមចុច [🔁 បង្កើតម្ដងទៀត] ដើម្បីសាកល្បងឡើងវិញ។"

    def _is_error_response(self, text: str) -> bool:
        if not text:
            return True
        s = text.strip()
        return s.startswith("⚠️") or s.startswith("❌") or "Error:" in s

    # ─────────────────────────────────────────────
    # Content Type Methods (Structured Shooting Plan)
    # ─────────────────────────────────────────────

    async def generate_content_by_type(
        self,
        content_type: str,
        topic: str,
        niche: str,
        duration: str = "60 វិនាទី",
        user_pace: float = DEFAULT_CHARS_PER_SECOND
    ) -> Tuple[str, Optional[ScriptPlan]]:
        """
        Generates a timestamped video script & shooting plan according to content format.
        Validates timeline rules in Python and calculates estimated speaking duration.
        Returns: (formatted_telegram_text, ScriptPlan)
        """
        target_s = parse_duration_seconds(duration)

        if content_type == "3whs":
            prompt = get_script_generation_prompt(topic, duration)
        elif content_type == "pov":
            prompt = get_pov_story_prompt(topic, niche, duration)
        elif content_type == "myth":
            prompt = get_myth_reality_prompt(topic, niche, duration)
        elif content_type == "transform":
            prompt = get_before_after_prompt(topic, niche, duration)
        elif content_type == "hottake":
            prompt = get_hot_take_prompt(topic, niche, duration)
        elif content_type == "toplist":
            prompt = get_top_list_prompt(topic, niche, duration)
        else:
            prompt = get_script_generation_prompt(topic, duration)

        raw_response = await self.generate_response(prompt, is_json=True)

        if self._is_error_response(raw_response):
            return raw_response, None

        # Parse, validate timeline, and check speaking pace
        plan = parse_and_validate_script_plan(raw_response, target_s, user_pace)

        # Format human-readable output for Telegram
        formatted_text = format_script_for_telegram(plan, user_pace)
        return formatted_text, plan

    async def refine_shorten(
        self,
        last_script_text: str,
        duration: str = "60 វិនាទី",
        user_pace: float = DEFAULT_CHARS_PER_SECOND
    ) -> Tuple[str, Optional[ScriptPlan]]:
        """
        Refines the script to make dialogue punchier and shorter.
        Re-validates the timeline and recalculates estimated speaking duration.
        """
        target_s = parse_duration_seconds(duration)
        prompt = get_refine_shorten_prompt(last_script_text, duration)
        raw_response = await self.generate_response(prompt, is_json=True)

        if self._is_error_response(raw_response):
            return raw_response, None

        plan = parse_and_validate_script_plan(raw_response, target_s, user_pace)
        formatted_text = format_script_for_telegram(plan, user_pace)
        return formatted_text, plan

    async def refine_hook(self, last_script: str) -> str:
        """
        Generate 3 alternative hooks for the script.
        This provides hook choices for the user and does NOT overwrite the full script.
        """
        prompt = get_refine_hook_prompt(last_script)
        return await self.generate_response(prompt, is_json=False)

    async def chat(self, user_message: str) -> str:
        """Free-text chat with 3WHs AI Coach"""
        prompt = get_chat_prompt(user_message)
        return await self.generate_response(prompt, is_json=False)

    # ─────────────────────────────────────────────
    # News-Grounded Daily Content Ideas
    # ─────────────────────────────────────────────

    async def generate_daily_ideas(self, category: str = "ទូទៅ") -> str:
        """
        Generate daily video content ideas.
        1. Checks in-memory cache for today's date (Asia/Phnom_Penh) and category.
        2. Retrieves verified fresh news items (< 48 hours).
        3. If fresh items exist and match category, passes numbered evidence to Gemini.
        4. Validates source IDs from Gemini output and generates verified Markdown links in Python.
        5. If retrieval fails, no recent items, or category has no news evidence, falls back honestly to general AI ideas.
        6. Avoids caching error messages.
        7. Concurrency locked to prevent duplicate Gemini calls from identical requests.
        """
        tz = pytz.timezone("Asia/Phnom_Penh")
        now_local = datetime.now(tz)
        local_date_str = now_local.strftime("%Y-%m-%d")
        retrieval_date_str = now_local.strftime("%d/%m/%Y %H:%M")
        cat_clean = category.strip() if category else "ទូទៅ"
        cat_key = cat_clean.lower()
        cache_key = f"{local_date_str}_{cat_key}"

        # 1. Fast cache check
        if cache_key in _DAILY_IDEAS_CACHE:
            logger.info(f"Reusing cached daily ideas for '{cache_key}'")
            return _DAILY_IDEAS_CACHE[cache_key]

        # 2. Concurrency lock to prevent simultaneous duplicate requests
        async with _IDEAS_LOCK:
            # Double check after acquiring lock
            if cache_key in _DAILY_IDEAS_CACHE:
                return _DAILY_IDEAS_CACHE[cache_key]

            # 3. Check if category is supported by fresh news sources
            news_items: List[NewsItem] = []
            is_news_supported = any(k in cat_key for k in ["general", "ទូទៅ", "business", "លក់", "អាជីវកម្ម", "សេដ្ឋកិច្ច", "tech", "បច្ចេកវិទ្យា", "កម្ពុជា", "cambodia"]) or cat_clean in ["General", "ទូទៅ", "មាតិកាទូទៅ និងអាជីវកម្ម"]

            if is_news_supported:
                try:
                    news_items = await get_fresh_news_sources(category=cat_clean, max_items=5)
                except Exception as e:
                    logger.warning(f"Error fetching fresh news: {e}")
                    news_items = []

            # 4. If fresh news items found: Evidence-based Generation
            if news_items:
                sources_lines = []
                for it in news_items:
                    date_display = it.published_at.strftime("%d/%m/%Y %H:%M UTC") if it.published_at else "កាលបរិច្ឆេទមិនបញ្ជាក់"
                    sources_lines.append(f"[{it.id}] ចំណងជើង: {it.title} | សារព័ត៌មាន: {it.publisher} (ចុះផ្សាយ: {date_display})")
                sources_text = "\n".join(sources_lines)

                prompt = get_news_grounded_ideas_prompt(sources_text, cat_clean)
                raw_response = await self.generate_response(prompt, is_json=False)

                # Check for error
                if self._is_error_response(raw_response):
                    return raw_response  # Do NOT cache errors

                # Validate source IDs referenced in Gemini's response
                referenced_ids = set()
                for match in re.finditer(r"\[(\d+)\]", raw_response):
                    try:
                        referenced_ids.add(int(match.group(1)))
                    except ValueError:
                        pass

                valid_item_ids = {it.id for it in news_items}
                valid_refs = referenced_ids.intersection(valid_item_ids)

                # Build verified sources block in Python using original validated URLs
                verified_links = []
                if valid_refs:
                    verified_links.append("\n━━━━━━━━━━━━━━━━━━━━━")
                    verified_links.append("🔗 **ប្រភពព័ត៌មានយោងពិតប្រាកដ (Verified Sources):**")
                    for item_id in sorted(valid_refs):
                        item = next(it for it in news_items if it.id == item_id)
                        pub_str = item.published_at.strftime("%d/%m/%Y") if item.published_at else "មិនបញ្ជាក់កាលបរិច្ឆេទ"
                        verified_links.append(f"• [{item.id}] [{item.publisher}: {item.title}]({item.url}) — _ចុះផ្សាយ: {pub_str}_")
                    verified_links.append(f"📅 _កាលបរិច្ឆេទទាញយកទិន្នន័យ (Retrieved): {retrieval_date_str} (Asia/Phnom_Penh)_")
                    verified_links.append("💡 _(គំនិតខាងលើត្រូវបានបង្កើតផ្អែកលើព័ត៌មានថ្មីៗក្នុងរយៈពេល ៤៨ ម៉ោងចុងក្រោយ មិនមែនជាទិន្នន័យ Trend ផ្ទាល់ពី TikTok/Facebook ឡើយ)_")
                else:
                    # If Gemini did not reference valid IDs, list the retrieved sources openly
                    verified_links.append("\n━━━━━━━━━━━━━━━━━━━━━")
                    verified_links.append("🔗 **បញ្ជីព័ត៌មានថ្មីៗដែលបានទាញយកមកពិនិត្យ៖**")
                    for item in news_items:
                        pub_str = item.published_at.strftime("%d/%m/%Y") if item.published_at else "មិនបញ្ជាក់កាលបរិច្ឆេទ"
                        verified_links.append(f"• [{item.publisher}: {item.title}]({item.url}) — _ចុះផ្សាយ: {pub_str}_")
                    verified_links.append(f"📅 _កាលបរិច្ឆេទទាញយកទិន្នន័យ (Retrieved): {retrieval_date_str} (Asia/Phnom_Penh)_")
                    verified_links.append("💡 _(គំនិតខាងលើត្រូវបានបំផុសចេញពីព័ត៌មានថ្មីៗក្នុងរយៈពេល ៤៨ ម៉ោងចុងក្រោយ មិនមែនជាទិន្នន័យ Trend ផ្ទាល់ពី TikTok/Facebook ឡើយ)_")

                final_output = (
                    "📰 *គំនិតមាតិកាផ្អែកលើព័ត៌មានថ្មីៗ*\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n\n"
                    + raw_response.strip()
                    + "\n"
                    + "\n".join(verified_links)
                )
                _DAILY_IDEAS_CACHE[cache_key] = final_output
                return final_output

            # 5. Honest Fallback: When no fresh items or unsupported category
            logger.info(f"No fresh news evidence for category '{cat_clean}'. Using honest fallback.")
            prompt = get_daily_ideas_prompt(cat_clean)
            raw_response = await self.generate_response(prompt, is_json=False)

            if self._is_error_response(raw_response):
                return raw_response  # Do NOT cache errors

            honest_header = (
                "💡 *គំនិតមាតិកាទូទៅពី AI*\n"
                "ℹ️ _(គំនិតទូទៅពី AI - មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ "
                + (f"ដោយសារមិនមានប្រភពព័ត៌មានថ្មីក្នុងវិស័យ {cat_clean}" if not is_news_supported else "ដោយសារមិនមានព័ត៌មានថ្មីសមស្របក្នុងរយៈពេល ៤៨ ម៉ោង")
                + ")_\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            clean_body = raw_response.replace("━━━━━━━━━━━━━━━━━━━━━\n💡 **គំនិតមាតិកាទូទៅពី AI**\nℹ️ _(គំនិតទូទៅពី AI - មិនបានផ្ទៀងផ្ទាត់ជាមួយព័ត៌មានថ្មីៗ)_\n━━━━━━━━━━━━━━━━━━━━━", "").strip()
            final_output = honest_header + clean_body
            _DAILY_IDEAS_CACHE[cache_key] = final_output
            return final_output
