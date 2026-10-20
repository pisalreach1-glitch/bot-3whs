"""
trend_sources.py - Public News RSS Retrieval & Verification for 3WHs Bot.

Zero additional spending, zero paid APIs.
Retrieves and validates fresh news items from publicly accessible RSS feeds.
Deduplicates, checks publication freshness within 48 hours, and caches feeds in memory.
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
MAX_FEED_BYTES = 350000  # Cap response size to ~350KB
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

# Verified publicly accessible RSS feeds (zero API keys required)
CONFIGURED_FEEDS = [
    {
        "publisher": "BBC News (Asia)",
        "url": "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
        "category": "general",
    },
    {
        "publisher": "Google News (Cambodia)",
        "url": "https://news.google.com/rss/search?q=Cambodia+when:2d&hl=en-US&gl=US&ceid=US:en",
        "category": "general",
    },
    {
        "publisher": "Al Jazeera (World)",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "general",
    },
    {
        "publisher": "Google News (Business)",
        "url": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en",
        "category": "business",
    },
    {
        "publisher": "Google News (Technology)",
        "url": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
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

def parse_rss_xml(xml_bytes: bytes, publisher: str, now_utc: datetime) -> List[NewsItem]:
    """Parses raw RSS XML bytes, validates items, and flags 48h freshness."""
    items: List[NewsItem] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception as e:
        logger.warning(f"Failed to parse XML from {publisher}: {e}")
        return items

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        pub_elem = item.find("pubDate")

        if title_elem is None or not title_elem.text:
            continue
        if link_elem is None or not link_elem.text:
            continue

        raw_title = html.unescape(title_elem.text.strip())
        raw_link = link_elem.text.strip()

        # Security: ensure link is a valid web URL
        if not (raw_link.startswith("http://") or raw_link.startswith("https://")):
            continue

        # Clean title from source suffixes like " - BBC News" or " - Reuters"
        clean_title = re.sub(r"\s*-\s*[A-Za-z0-9\s\.\(\)]+$", "", raw_title).strip()
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
            publisher=publisher,
            url=raw_link,
            published_at=pub_dt,
            is_recent=is_recent,
        ))

    return items

async def fetch_single_feed(feed_cfg: dict, client: httpx.AsyncClient, now_utc: datetime) -> List[NewsItem]:
    """Fetches a single RSS feed with timeout and size cap."""
    publisher = feed_cfg["publisher"]
    url = feed_cfg["url"]
    try:
        response = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            logger.warning(f"Feed {publisher} returned status {response.status_code}")
            return []
        
        # Enforce size limit
        content = response.content[:MAX_FEED_BYTES]
        return parse_rss_xml(content, publisher, now_utc)
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching feed {publisher}")
        return []
    except Exception as e:
        logger.warning(f"Error fetching feed {publisher}: {e}")
        return []

async def get_fresh_news_sources(category: str = "general", max_items: int = 5) -> List[NewsItem]:
    """
    Retrieves fresh news items published within the last 48 hours.
    Deduplicates by URL and normalized title.
    Caches results for 1 hour to save network & quota.
    """
    now_utc = datetime.now(timezone.utc)
    cat_key = category.lower().strip()
    if any(k in cat_key for k in ["business", "e-commerce", "លក់", "អាជីវកម្ម", "សេដ្ឋកិច្ច"]):
        target_cat = "business"
    elif any(k in cat_key for k in ["tech", "digital", "ទូរស័ព្ទ", "កាត់ត", "បច្ចេកវិទ្យា"]):
        target_cat = "tech"
    else:
        target_cat = "general"

    # Check in-memory cache
    async with _FETCH_LOCK:
        if target_cat in _FEED_CACHE:
            cached_time, cached_items = _FEED_CACHE[target_cat]
            if (now_utc - cached_time).total_seconds() < FEED_CACHE_TTL_SECONDS:
                logger.info(f"Reusing cached feed items for '{target_cat}' ({len(cached_items)} items)")
                return cached_items[:max_items]

        # Select feeds for this category
        selected_feeds = [f for f in CONFIGURED_FEEDS if f["category"] == target_cat]
        if not selected_feeds or target_cat != "general":
            # Include general feeds as fallback
            selected_feeds += [f for f in CONFIGURED_FEEDS if f["category"] == "general"]

        all_items: List[NewsItem] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 3WHsBot/2.0"
        }
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            tasks = [fetch_single_feed(cfg, client, now_utc) for cfg in selected_feeds]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list):
                    all_items.extend(res)

        # Deduplicate by URL and normalized title
        seen_urls = set()
        seen_titles = set()
        deduped: List[NewsItem] = []

        # Sort so that verified recent items (within 48h) come first
        all_items.sort(key=lambda x: (x.is_recent, x.published_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)

        for item in all_items:
            # We strictly require recent items for fresh news claims
            if not item.is_recent:
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

        logger.info(f"Retrieved {len(final_items)} fresh news items for category '{target_cat}'")
        return final_items

def clear_feed_cache():
    """Helper for testing cache behavior."""
    _FEED_CACHE.clear()
