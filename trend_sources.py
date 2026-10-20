"""
trend_sources.py - Public News RSS Retrieval & Verification for 3WHs Bot.

Zero additional spending, zero paid APIs.
Retrieves and validates fresh news items from publicly accessible RSS feeds.
Deduplicates, checks publication freshness within 48 hours, and caches feeds in memory.
Enforces streaming HTTP size limits, word-boundary relevance filtering, and source metadata extraction.
"""

import logging
import re
import html
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import httpx
import pytz

logger = logging.getLogger(__name__)

PHNOM_PENH_TZ = pytz.timezone("Asia/Phnom_Penh")
MAX_FEED_BYTES = 350000  # Cap response stream to ~350KB
REQUEST_TIMEOUT_SECONDS = 8.0
FEED_CACHE_TTL_SECONDS = 3600  # 1 hour cache

@dataclass
class NewsItem:
    id: int
    title: str
    publisher: str
    url: str
    published_at: Optional[datetime] = None
    is_recent: bool = False

# Verified publicly accessible RSS feeds focusing strictly on Cambodia (zero API keys required)
CONFIGURED_FEEDS = [
    {
        "publisher": "Google News (Cambodia)",
        "url": "https://news.google.com/rss/search?q=Cambodia+when:3d&hl=en-US&gl=KH&ceid=KH:en",
        "category": "general",
    },
    {
        "publisher": "Google News (Cambodia Business)",
        "url": "https://news.google.com/rss/search?q=Cambodia+business+economy+when:3d&hl=en-US&gl=KH&ceid=KH:en",
        "category": "business",
    },
    {
        "publisher": "Google News (Cambodia Technology)",
        "url": "https://news.google.com/rss/search?q=Cambodia+technology+OR+digital+when:3d&hl=en-US&gl=KH&ceid=KH:en",
        "category": "tech",
    },
]

# In-memory feed cache: category -> (timestamp, list of NewsItem)
_FEED_CACHE: Dict[str, Tuple[datetime, List[NewsItem]]] = {}
_FETCH_LOCK = asyncio.Lock()

def normalize_title(title: str) -> str:
    """Normalize a title string for deduplication."""
    cleaned = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(cleaned.split())

def parse_pub_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse RSS pubDate to a timezone-aware datetime. Does NOT invent missing dates."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def parse_rss_xml(xml_bytes: bytes, default_publisher: str, now_utc: datetime) -> List[NewsItem]:
    """Parses raw RSS XML bytes, validates items, extracts actual publisher, and flags 48h freshness."""
    items: List[NewsItem] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        logger.warning(f"Failed to parse XML from {default_publisher}: {e}")
        return items

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        pub_elem = item.find("pubDate")
        source_elem = item.find("source")

        if title_elem is None or not title_elem.text:
            continue
        if link_elem is None or not link_elem.text:
            continue

        raw_title = html.unescape(title_elem.text.strip())
        raw_link = link_elem.text.strip()

        # Security: ensure link is a valid web URL
        if not (raw_link.startswith("http://") or raw_link.startswith("https://")):
            continue

        # Extract actual publisher if available in <source> tag
        actual_publisher = default_publisher
        if source_elem is not None and source_elem.text:
            sub_pub = html.unescape(source_elem.text.strip())
            if sub_pub:
                if "Google News" in default_publisher:
                    actual_publisher = f"{sub_pub} (via Google News)"
                else:
                    actual_publisher = sub_pub

        # Clean title from source suffixes like " - BBC News" or " - Reuters"
        clean_title = re.sub(r"\s*-\s*[A-Za-z0-9\s\.\(\)\&]+$", "", raw_title).strip()
        if not clean_title:
            clean_title = raw_title

        pub_dt = parse_pub_date(pub_elem.text if pub_elem is not None else None)
        is_recent = False
        if pub_dt:
            # Check 48 hour freshness
            age = now_utc - pub_dt.astimezone(timezone.utc)
            if timedelta(seconds=0) <= age <= timedelta(hours=48):
                is_recent = True

        items.append(NewsItem(
            id=0,  # will be assigned during deduplication
            title=clean_title,
            publisher=actual_publisher,
            url=raw_link,
            published_at=pub_dt,
            is_recent=is_recent,
        ))

    return items

async def fetch_single_feed(feed_cfg: dict, client: httpx.AsyncClient, now_utc: datetime) -> List[NewsItem]:
    """Fetches a single RSS feed with timeout and streaming response-size cap."""
    publisher = feed_cfg["publisher"]
    url = feed_cfg["url"]
    try:
        chunks = []
        total_bytes = 0
        async with client.stream("GET", url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status_code != 200:
                logger.warning(f"Feed {publisher} returned status {response.status_code}")
                return []
            async for chunk in response.aiter_bytes():
                total_bytes += len(chunk)
                if total_bytes > MAX_FEED_BYTES:
                    excess = total_bytes - MAX_FEED_BYTES
                    if len(chunk) > excess:
                        chunks.append(chunk[:-excess])
                    break
                chunks.append(chunk)

        content = b"".join(chunks)
        return parse_rss_xml(content, publisher, now_utc)
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching feed {publisher}")
        return []
    except Exception as e:
        logger.warning(f"Error fetching feed {publisher}: {e}")
        return []

# Category regex with strict word-boundary matching to prevent substring bugs (e.g. 'ai' matching 'said')
CATEGORY_REGEX = {
    "business": re.compile(
        r"\b(business|markets?|economy|companies|company|trade|finance|financial|investing|investment|banks?|banking|industry|startups?|retail|profits?|revenues?|prices?|commercial|sales?|stocks?|dollars?|exports?|imports?|riel|gdp)\b",
        re.IGNORECASE
    ),
    "tech": re.compile(
        r"\b(tech|technology|ai|artificial intelligence|software|apps?|phones?|digital|cyber|google|apple|microsoft|devices?|internet|chips?|startups?|robotics?|robots?|gaming|games?|cloud|meta|nvidia|hardware|systems?)\b",
        re.IGNORECASE
    )
}

def is_item_relevant_to_category(item: NewsItem, target_cat: str) -> bool:
    """Checks if an item's title matches the target category using word boundaries."""
    if target_cat == "general":
        return True
    pattern = CATEGORY_REGEX.get(target_cat)
    if not pattern:
        return True
    return bool(pattern.search(item.title))

async def get_fresh_news_sources(category: str = "general", max_items: int = 5) -> List[NewsItem]:
    """
    Retrieves fresh news items published within the last 48 hours.
    Prioritizes dedicated category feeds and checks relevance with regex word boundaries.
    Deduplicates by URL and normalized title.
    Rechecks 48-hour freshness when returning cached items.
    Avoids fetching general feeds twice when target_cat is 'general'.
    """
    now_utc = datetime.now(timezone.utc)
    cat_key = category.lower().strip()
    if any(k in cat_key for k in ["business", "e-commerce", "លក់", "អាជីវកម្ម", "សេដ្ឋកិច្ច"]):
        target_cat = "business"
    elif any(k in cat_key for k in ["tech", "digital", "ទូរស័ព្ទ", "កាត់ត", "បច្ចេកវិទ្យា"]):
        target_cat = "tech"
    else:
        target_cat = "general"

    # Check in-memory cache and revalidate freshness
    async with _FETCH_LOCK:
        if target_cat in _FEED_CACHE:
            cached_time, cached_items = _FEED_CACHE[target_cat]
            if (now_utc - cached_time).total_seconds() < FEED_CACHE_TTL_SECONDS:
                fresh_cached = []
                for it in cached_items:
                    if it.published_at:
                        age = now_utc - it.published_at.astimezone(timezone.utc)
                        if timedelta(seconds=0) <= age <= timedelta(hours=48):
                            fresh_cached.append(it)
                    elif it.is_recent:
                        fresh_cached.append(it)
                if fresh_cached:
                    logger.info(f"Reusing {len(fresh_cached)} fresh cached feed items for '{target_cat}'")
                    return fresh_cached[:max_items]

        all_items: List[NewsItem] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3WHsBot/2.0"
        }

        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            if target_cat == "general":
                # For general category, fetch general feeds exactly once
                general_feeds = [f for f in CONFIGURED_FEEDS if f["category"] == "general"]
                tasks = [fetch_single_feed(cfg, client, now_utc) for cfg in general_feeds]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, list):
                        all_items.extend(res)
            else:
                # Specialized category (business or tech)
                category_feeds = [f for f in CONFIGURED_FEEDS if f["category"] == target_cat]
                general_feeds = [f for f in CONFIGURED_FEEDS if f["category"] == "general"]

                if category_feeds:
                    tasks = [fetch_single_feed(cfg, client, now_utc) for cfg in category_feeds]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, list):
                            all_items.extend(res)

                # Only fetch general feeds if category feeds returned fewer than max_items
                if len(all_items) < max_items:
                    tasks = [fetch_single_feed(cfg, client, now_utc) for cfg in general_feeds]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, list):
                            for item in res:
                                if is_item_relevant_to_category(item, target_cat):
                                    all_items.append(item)

        # Deduplicate by URL and normalized title
        seen_urls = set()
        seen_titles = set()
        deduped: List[NewsItem] = []

        # Sort: verified recent items (<48h) first, with category feed items prioritized
        all_items.sort(
            key=lambda x: (
                x.is_recent,
                is_item_relevant_to_category(x, target_cat),
                x.published_at or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True
        )

        for item in all_items:
            if not item.is_recent:
                continue

            # Ensure strict relevance for specialized categories
            if target_cat != "general" and not is_item_relevant_to_category(item, target_cat):
                continue

            norm_t = normalize_title(item.title)
            if item.url in seen_urls or norm_t in seen_titles:
                continue

            seen_urls.add(item.url)
            seen_titles.add(norm_t)
            deduped.append(item)

        # Assign clean numeric IDs: 1, 2, 3...
        for idx, item in enumerate(deduped, start=1):
            item.id = idx

        final_items = deduped[:max_items]
        if final_items:
            _FEED_CACHE[target_cat] = (now_utc, final_items)

        logger.info(f"Retrieved {len(final_items)} relevant fresh news items for category '{target_cat}'")
        return final_items

def clear_feed_cache():
    """Helper for testing cache behavior."""
    _FEED_CACHE.clear()
