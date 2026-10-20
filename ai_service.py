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
    PlanResult,
    parse_duration_seconds,
    validate_and_build_plan,
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
MAX_CONCURRENT_API_CALLS = 5
_API_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_API_CALLS)

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

    async def _generate_with_model(self, model_name: str, prompt: str, is_json: bool = False) -> str:
        """Native async SDK generation call without thread-offload leaks."""
        if self.sdk_type == "google-genai":
            from google.genai import types
            config_kwargs = {
                "system_instruction": SYSTEM_INSTRUCTION,
                "temperature": 0.7,
            }
            if is_json:
                config_kwargs["response_mime_type"] = "application/json"
            
            response = await self.client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs)
            )
            if response and response.text:
                return response.text
            raise ValueError(f"Empty response text from {model_name}")

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
            response = await model.generate_content_async(prompt)
            if response and response.text:
                return response.text
            raise ValueError(f"Empty response text from {model_name}")

        else:
            raise RuntimeError("No Gemini SDK configured")

    async def generate_response(self, prompt: str, is_json: bool = False) -> str:
        """
        Generates response using native async SDK with bounded concurrency and transport timeout.
        Does not continue through fallback models if timeout or cancellation occurs.
        """
        if not self.is_configured():
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
            self._init_client()
            if not self.is_configured():
                self.last_api_status = "🔴 ខ្វះ API Key"
                return "⚠️ សូមបញ្ចូល `GEMINI_API_KEY` នៅក្នុង file `.env` ជាមុនសិន!"

        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]

        async with _API_SEMAPHORE:
            errors = []
            for model_name in models_to_try:
                try:
                    text = await asyncio.wait_for(
                        self._generate_with_model(model_name, prompt, is_json),
                        timeout=REQUEST_TIMEOUT_SECONDS
                    )
                    self.last_api_status = "🟢 ដំណើរការល្អ (Online)"
                    return text
                except asyncio.CancelledError:
                    logger.info(f"API request was cancelled during {model_name}")
                    raise
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout on model {model_name}. Halting fallback to save quota.")
                    self.last_api_status = "⚠️ Request Timeout"
                    return (
                        "⚠️ **សំណើចំណាយពេលយូរពេក (Request Timeout)**\n\n"
                        "ប្រព័ន្ធ AI មិនបានឆ្លើយតបទាន់ពេលវេលាឡើយ។\n"
                        "សូមចុច [🔁 បង្កើតម្ដងទៀត] ដើម្បីសាកល្បងឡើងវិញ។"
                    )
                except Exception as e:
                    err_str = str(e)
                    logger.warning(f"Model {model_name} failed: {err_str}")
                    errors.append(f"{model_name}: {err_str}")
                    if "429" in err_str.lower() or "quota" in err_str.lower() or "exhausted" in err_str.lower():
                        self.last_api_status = "⚠️ Quota Limit"
                        return (
                            "⚠️ **ប្រព័ន្ធ AI ទទួលសំណើច្រើន ឬដល់កម្រិតកំណត់បណ្ដោះអាសន្ន (Quota Limit)**\n\n"
                            "Google Gemini Free Tier កំពុងរង់ចាំ Reset សំណើបន្តិច។\n"
                            "👉 សូមរង់ចាំមួយស្របក់ រួចចុចប៊ូតុង **[🔁 បង្កើតម្ដងទៀត]** នោះវានឹងដំណើរការវិញជាធម្មតា!"
                        )
                    continue

            self.last_api_status = f"🔴 Error: {errors[-1][:50] if errors else 'Unknown'}"
            return (
                f"❌ **AI មិនទាន់អាចឆ្លើយតបបាននៅពេលនេះ**\n\n"
                f"មូលហេតុ: {errors[-1] if errors else 'High Demand'}\n\n"
                "🔄 _សូមចុចប៊ូតុង [🔁 បង្កើតម្ដងទៀត] ក្នុងរយៈពេលខ្លីខាងមុខ!_"
            )

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
    ) -> PlanResult:
        """
        Generates a timestamped video script & shooting plan according to content format.
        Validates timeline rules in Python and calculates estimated speaking duration.
        Returns: PlanResult (explicit success contract).
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
            return PlanResult(
                success=False,
                plan=None,
                formatted_text=raw_response,
                error_message="AI generation returned error message",
            )

        return validate_and_build_plan(raw_response, target_s, user_pace)

    async def refine_shorten(
        self,
        last_script_text: str,
        duration: str = "60 វិនាទី",
        user_pace: float = DEFAULT_CHARS_PER_SECOND
    ) -> PlanResult:
        """
        Refines the script to make dialogue punchier and shorter.
        Re-validates the timeline and recalculates estimated speaking duration.
        Returns: PlanResult.
        """
        target_s = parse_duration_seconds(duration)
        prompt = get_refine_shorten_prompt(last_script_text, duration)
        raw_response = await self.generate_response(prompt, is_json=True)

        if self._is_error_response(raw_response):
            return PlanResult(
                success=False,
                plan=None,
                formatted_text=raw_response,
                error_message="AI shortening returned error message",
            )

        return validate_and_build_plan(raw_response, target_s, user_pace)

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
        4. Validates source IDs:
           - Rejects if ANY referenced ID is invalid (e.g. [99]).
           - Rejects if NO valid references exist.
           - Validates references for each idea.
           - On citation failure: NEVER makes an automatic second Gemini call. Returns retrieved sources with Khmer notice.
           - Builds source links ONLY in Python from retrieved records.
        5. If retrieval fails or category has no evidence, falls back honestly to general AI ideas.
        6. Avoids caching error or failure messages.
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

                # Check for API error
                if self._is_error_response(raw_response):
                    return raw_response  # Do NOT cache errors

                # ── Strict Source Validation ──
                # A. Collect all [N] references across the response
                all_ref_matches = re.findall(r"\[(\d+)\]", raw_response)
                referenced_ids = set()
                for m in all_ref_matches:
                    try:
                        referenced_ids.add(int(m))
                    except ValueError:
                        pass

                valid_item_ids = {it.id for it in news_items}
                invalid_refs = referenced_ids - valid_item_ids
                valid_refs = referenced_ids.intersection(valid_item_ids)

                citation_failure_reason = None
                if not valid_refs:
                    citation_failure_reason = "គ្មានការយោងប្រភពលេខ [ID] ត្រឹមត្រូវណាមួយឡើយ"
                elif invalid_refs:
                    citation_failure_reason = f"មានការយោងលេខប្រភពដែលមិនមានក្នុងបញ្ជី {sorted(list(invalid_refs))}"

                # B. Validate per idea if structured ideas are present
                idea_blocks = re.split(r"(?=(?:🔥\s*\*\*គំនិត|ប្រធានបទ)ទី\s*\d+)", raw_response)
                valid_idea_blocks = [b for b in idea_blocks if re.search(r"(?:🔥\s*\*\*គំនិត|ប្រធានបទ)ទី\s*\d+", b)]
                if valid_idea_blocks:
                    for idx, block in enumerate(valid_idea_blocks, start=1):
                        block_refs = set(int(x) for x in re.findall(r"\[(\d+)\]", block) if x.isdigit())
                        block_valid = block_refs.intersection(valid_item_ids)
                        block_invalid = block_refs - valid_item_ids
                        if block_invalid:
                            citation_failure_reason = f"គំនិតទី {idx} យោងលេខប្រភពមិនត្រឹមត្រូវ {sorted(list(block_invalid))}"
                            break
                        if not block_valid:
                            citation_failure_reason = f"គំនិតទី {idx} ខ្វះការយោងប្រភពពិតប្រាកដ"
                            break

                # If citation failed: REJECT immediately. Do NOT call Gemini again. Show retrieved sources.
                if citation_failure_reason:
                    logger.warning(f"Citation verification rejected: {citation_failure_reason}. Showing retrieved sources without second Gemini call.")
                    sources_footnote = "\n".join(
                        f"• [{item.id}] [{item.publisher}: {item.title}]({item.url})"
                        for item in news_items
                    )
                    failure_output = (
                        "⚠️ *ការផ្ទៀងផ្ទាត់ប្រភពព័ត៌មានមិនត្រឹមត្រូវ (Citation Verification Failed)*\n\n"
                        f"មូលហេតុ៖ _{citation_failure_reason}_\n"
                        "ដើម្បីធានានូវភាពត្រឹមត្រូវ និងទប់ស្កាត់ការប្រឌិតព័ត៌មាន AI មិនត្រូវបានអនុញ្ញាតឱ្យបង្ហាញគំនិតដែលគ្មានការបញ្ជាក់ប្រភពច្បាស់លាស់ឡើយ។\n\n"
                        "🔗 **បញ្ជីព័ត៌មានថ្មីៗដែលបានទាញយកជាក់ស្តែង៖**\n"
                        f"{sources_footnote}\n\n"
                        "💡 _អ្នកអាចសាកល្បងចុច [🔁 បង្កើតម្ដងទៀត] ឬប្រើពាក្យបញ្ជា /ideas ធម្មតាដើម្បីទទួលគំនិតទូទៅពី AI។_"
                    )
                    return failure_output  # Do NOT cache failure

                # C. Citations are valid: Build verified source links ONLY in Python from retrieved records
                verified_links = [
                    "\n━━━━━━━━━━━━━━━━━━━━━",
                    "🔗 **ប្រភពព័ត៌មានយោងពិតប្រាកដ (Verified Sources):**"
                ]
                for item_id in sorted(valid_refs):
                    item = next(it for it in news_items if it.id == item_id)
                    pub_str = item.published_at.strftime("%d/%m/%Y") if item.published_at else "មិនបញ្ជាក់កាលបរិច្ឆេទ"
                    verified_links.append(f"• [{item.id}] [{item.publisher}: {item.title}]({item.url}) — _ចុះផ្សាយ: {pub_str}_")
                verified_links.append(f"📅 _កាលបរិច្ឆេទទាញយកទិន្នន័យ (Retrieved): {retrieval_date_str} (Asia/Phnom_Penh)_")
                verified_links.append("💡 _(គំនិតខាងលើត្រូវបានបង្កើតផ្អែកលើព័ត៌មានថ្មីៗក្នុងរយៈពេល ៤៨ ម៉ោងចុងក្រោយ មិនមែនជាទិន្នន័យ Trend ផ្ទាល់ពី TikTok/Facebook ឡើយ)_")

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
