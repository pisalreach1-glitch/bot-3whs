"""
app/services/ideas.py - Daily Video Content Ideas Generation and Citation Verification.

Retrieves verified fresh news (<48h), validates source citations strictly per idea,
deduplicates generation, caches daily results, and saves idea batches for user selection.
"""

import re
import uuid
import asyncio
import logging
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import pytz

from app.models import UserKey, Idea, EvidenceRecord
from app.storage import Storage
from ai_service import AIService
from trend_sources import get_fresh_news_sources, NewsItem
from prompts import get_news_grounded_ideas_prompt, get_daily_ideas_prompt

logger = logging.getLogger(__name__)

# Daily ideas cache keyed by "YYYY-MM-DD_category"
_DAILY_IDEAS_CACHE: Dict[str, Tuple[List[Idea], List[EvidenceRecord]]] = {}
_IDEAS_LOCK = asyncio.Lock()

def clear_daily_ideas_cache():
    """Clear cached daily ideas (useful for testing)."""
    _DAILY_IDEAS_CACHE.clear()

def parse_generated_ideas(text: str, default_format: str = "3whs") -> List[Idea]:
    """Parses numbered ideas from Gemini output into structured Idea objects."""
    ideas: List[Idea] = []
    # Split by idea markers
    blocks = re.split(r"(?=(?:🔥\s*\*\*គំនិត|ប្រធានបទ)ទី\s*\d+)", text)
    valid_blocks = [b.strip() for b in blocks if re.search(r"(?:🔥\s*\*\*គំនិត|ប្រធានបទ)ទី\s*\d+", b)]

    if not valid_blocks:
        # Fallback to general numbered points
        blocks = re.split(r"(?=\b\d+\.\s+)", text)
        valid_blocks = [b.strip() for b in blocks if re.search(r"^\d+\.\s+", b.strip())]

    for idx, block in enumerate(valid_blocks, start=1):
        # Extract title/topic
        title_match = re.search(r"(?:🔥\s*\*\*គំនិត|ប្រធានបទ)ទី\s*\d+[៖:\s]+([^\n\*]+)", block)
        if not title_match:
            title_match = re.search(r"^\d+\.\s*([^\n\*]+)", block)
        topic = title_match.group(1).strip() if title_match else f"គំនិតមាតិកាទី {idx}"

        # Extract hook
        hook_match = re.search(r"🎯\s*\*\*Hook\*\*[៖:\s]+([^\n]+)", block)
        hook = hook_match.group(1).strip() if hook_match else topic

        # Extract recommended format
        fmt = default_format
        if "POV" in block:
            fmt = "pov"
        elif "Myth" in block:
            fmt = "myth"
        elif "Before" in block or "មុន" in block:
            fmt = "transform"
        elif "Hot Take" in block or "មតិ" in block:
            fmt = "hottake"
        elif "Top" in block or "បញ្ជី" in block:
            fmt = "toplist"

        # Extract source IDs [N]
        refs = [int(m) for m in re.findall(r"\[(\d+)\]", block) if m.isdigit()]

        ideas.append(Idea(
            id=idx,
            topic=topic,
            hook=hook,
            suggested_format=fmt,
            source_ids=refs,
            evidence_status="verified" if refs else "ai_only",
        ))

    return ideas

async def get_or_generate_ideas(
    user_key: UserKey,
    category: str,
    storage: Storage,
    ai: AIService,
    force_ai_only: bool = False,
) -> Tuple[Optional[str], List[Idea], List[EvidenceRecord], Optional[str]]:
    """
    Returns (batch_token, ideas_list, evidence_list, failure_message).
    On citation failure: returns (None, [], evidence_list, failure_message)
    without triggering a second Gemini call.
    Uses daily caching (Asia/Phnom_Penh) and asyncio locking to deduplicate identical requests.
    """
    cat_clean = category.strip() if category else "ទូទៅ"
    cat_lower = cat_clean.lower()
    local_date_str = datetime.now(pytz.timezone("Asia/Phnom_Penh")).strftime("%Y-%m-%d")
    cache_key = f"{local_date_str}_{cat_lower}"

    # 1. Fast cache check before acquiring lock
    if not force_ai_only and cache_key in _DAILY_IDEAS_CACHE:
        cached_ideas, cached_evidence = _DAILY_IDEAS_CACHE[cache_key]
        logger.info(f"Reusing cached daily ideas for '{cache_key}'")
        batch_token = f"b_{uuid.uuid4().hex[:8]}"
        storage.save_idea_batch(batch_token, user_key, cat_clean, cached_ideas, cached_evidence)
        return batch_token, cached_ideas, cached_evidence, None

    # 2. Concurrency lock to prevent simultaneous duplicate requests
    async with _IDEAS_LOCK:
        # Double check after acquiring lock
        if not force_ai_only and cache_key in _DAILY_IDEAS_CACHE:
            cached_ideas, cached_evidence = _DAILY_IDEAS_CACHE[cache_key]
            logger.info(f"Reusing cached daily ideas after lock for '{cache_key}'")
            batch_token = f"b_{uuid.uuid4().hex[:8]}"
            storage.save_idea_batch(batch_token, user_key, cat_clean, cached_ideas, cached_evidence)
            return batch_token, cached_ideas, cached_evidence, None

        is_supported = any(k in cat_lower for k in ["general", "ទូទៅ", "business", "លក់", "អាជីវកម្ម", "សេដ្ឋកិច្ច", "tech", "បច្ចេកវិទ្យា", "cambodia", "កម្ពុជា"])
        evidence_records: List[EvidenceRecord] = []

        # Retrieve news evidence if supported and not forced AI-only
        if is_supported and not force_ai_only:
            try:
                news_items = await get_fresh_news_sources(category=cat_clean, max_items=5)
                for it in news_items:
                    evidence_records.append(EvidenceRecord(
                        id=str(it.id),
                        url=it.url,
                        platform_or_feed="news_rss",
                        publisher=it.publisher,
                        retrieved_at=datetime.now(pytz.timezone("Asia/Phnom_Penh")),
                        title=it.title,
                        published_at=it.published_at,
                    ))
            except Exception as e:
                logger.warning(f"Error fetching news sources for ideas: {e}")
                evidence_records = []

        # Case A: News Evidence Exists -> Grounded Generation
        if evidence_records:
            sources_lines = []
            for ev in evidence_records:
                pub_date = ev.published_at.strftime("%d/%m/%Y") if ev.published_at else "ថ្មីៗ"
                sources_lines.append(f"[{ev.id}] ចំណងជើង: {ev.title} | សារព័ត៌មាន: {ev.publisher} ({pub_date})")
            sources_text = "\n".join(sources_lines)

            prompt = get_news_grounded_ideas_prompt(sources_text, cat_clean)
            raw_response = await ai.generate_response(prompt, is_json=False)

            if ai._is_error_response(raw_response):
                return None, [], evidence_records, raw_response

            # Strict Citation Verification
            valid_ids = {int(ev.id) for ev in evidence_records}
            all_referenced_ids = set()
            for m in re.findall(r"\[(\d+)\]", raw_response):
                if m.isdigit():
                    all_referenced_ids.add(int(m))

            invalid_refs = all_referenced_ids - valid_ids
            valid_refs = all_referenced_ids.intersection(valid_ids)

            citation_failure = None
            if not valid_refs:
                citation_failure = "គ្មានការយោងលេខប្រភព [ID] ត្រឹមត្រូវណាមួយឡើយ"
            elif invalid_refs:
                citation_failure = f"មានការយោងលេខប្រភពដែលមិនមានក្នុងបញ្ជី {sorted(list(invalid_refs))}"

            # Per-idea check
            parsed_ideas = parse_generated_ideas(raw_response)
            if parsed_ideas:
                for idea in parsed_ideas:
                    idea_invalid = set(idea.source_ids) - valid_ids
                    if idea_invalid:
                        citation_failure = f"គំនិតទី {idea.id} យោងលេខប្រភពមិនត្រឹមត្រូវ {sorted(list(idea_invalid))}"
                        break
                    if not set(idea.source_ids).intersection(valid_ids):
                        citation_failure = f"គំនិតទី {idea.id} ខ្វះការយោងប្រភពពិតប្រាកដ"
                        break

            if citation_failure:
                logger.warning(f"Ideas citation failed: {citation_failure}. Halting second call.")
                sources_md = "\n".join(
                    f"• [{ev.id}] [{ev.publisher}: {ev.title}]({ev.url})"
                    for ev in evidence_records
                )
                msg = (
                    "⚠️ *ការផ្ទៀងផ្ទាត់ប្រភពព័ត៌មានមិនត្រឹមត្រូវ (Citation Verification Failed)*\n\n"
                    f"មូលហេតុ៖ _{citation_failure}_\n"
                    "ដើម្បីធានានូវភាពត្រឹមត្រូវ AI មិនត្រូវបានអនុញ្ញាតឱ្យបង្ហាញគំនិតដែលគ្មានប្រភពច្បាស់លាស់ឡើយ។\n\n"
                    "🔗 **បញ្ជីព័ត៌មានថ្មីៗដែលបានទាញយកជាក់ស្តែង៖**\n"
                    f"{sources_md}\n\n"
                    "💡 _អ្នកអាចសាកល្បងចុច [💡 រកគំនិតមាតិកា] ម្តងទៀត ឬជ្រើសរើសគំនិតទូទៅពី AI (AI-only)។_"
                )
                return None, [], evidence_records, msg

            # Citations are valid: cache results and store batch
            _DAILY_IDEAS_CACHE[cache_key] = (parsed_ideas, evidence_records)
            batch_token = f"b_{uuid.uuid4().hex[:8]}"
            storage.save_idea_batch(batch_token, user_key, cat_clean, parsed_ideas, evidence_records)
            return batch_token, parsed_ideas, evidence_records, None

        # Case B: Honest AI-only Fallback
        logger.info(f"Generating honest AI-only ideas for '{cat_clean}'")
        prompt = get_daily_ideas_prompt(cat_clean)
        raw_response = await ai.generate_response(prompt, is_json=False)

        if ai._is_error_response(raw_response):
            return None, [], [], raw_response

        parsed_ideas = parse_generated_ideas(raw_response)
        for i in parsed_ideas:
            i.evidence_status = "ai_only"
            i.source_ids = []

        _DAILY_IDEAS_CACHE[cache_key] = (parsed_ideas, [])
        batch_token = f"b_{uuid.uuid4().hex[:8]}"
        storage.save_idea_batch(batch_token, user_key, cat_clean, parsed_ideas, [])
        return batch_token, parsed_ideas, [], None
