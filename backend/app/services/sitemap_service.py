from urllib.parse import urlparse
from typing import Optional

import httpx
from defusedxml import ElementTree as ET

from app.models import KeywordPriorities, UrlResult


# Sitemap namespace
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
URLSET_TAG = "{%s}urlset" % SITEMAP_NS["sm"]
SITEMAPINDEX_TAG = "{%s}sitemapindex" % SITEMAP_NS["sm"]
URL_TAG = "{%s}url" % SITEMAP_NS["sm"]
LOC_TAG = "{%s}loc" % SITEMAP_NS["sm"]
LASTMOD_TAG = "{%s}lastmod" % SITEMAP_NS["sm"]

# Fallback for sitemaps without namespace
TAG_LOC = "loc"
TAG_LASTMOD = "lastmod"


def _get_text(el, tag: str, default: Optional[str] = None) -> Optional[str]:
    if el is None:
        return default
    child = el.find(tag, SITEMAP_NS)
    if child is None:
        child = el.find(f"sm:{tag}", SITEMAP_NS)
    if child is None:
        # no namespace
        for c in el:
            if c.tag == tag or (hasattr(c.tag, "endswith") and c.tag.endswith(tag)):
                return (c.text or "").strip() or default
        return default
    return (child.text or "").strip() or default


def _tag_local_name(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _extract_urls_from_xml(content: str) -> tuple[list[tuple[str, Optional[str]]], bool]:
    """
    Parse sitemap XML. Returns (list of (url, lastmod), is_index).
    If is_index True, URLs are child sitemap URLs to fetch.
    """
    root = ET.fromstring(content)
    results: list[tuple[str, Optional[str]]] = []
    root_local = _tag_local_name(root.tag or "")

    # Sitemap index: list of sitemap URLs
    if root_local == "sitemapindex":
        for sitemap_el in root:
            loc = _get_text(sitemap_el, "loc")
            if loc:
                results.append((loc.strip(), None))
        return results, True

    # URL set
    if root_local == "urlset":
        for url_el in root:
            if _tag_local_name(url_el.tag or "") != "url":
                continue
            loc = _get_text(url_el, "loc")
            if not loc:
                continue
            lastmod = _get_text(url_el, "lastmod")
            results.append((loc.strip(), lastmod))
    return results, False


def _url_depth(url: str) -> int:
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if not path:
        return 0
    return len(path.split("/"))


def _score_url(path_lower: str, keywords: KeywordPriorities) -> tuple[int, str]:
    """
    Score URL path against keywords. Returns (score, best_category).
    High=3, Medium=2, Low=1. Best category = highest contributing category.
    """
    high_score = sum(3 for k in keywords.High if k.lower() in path_lower)
    medium_score = sum(2 for k in keywords.Medium if k.lower() in path_lower)
    low_score = sum(1 for k in keywords.Low if k.lower() in path_lower)

    total = high_score + medium_score + low_score
    if total == 0:
        return 0, "Unmatched"

    # Best category = category that contributed the most (by weight)
    if high_score >= medium_score and high_score >= low_score and high_score > 0:
        best = "High"
    elif medium_score >= low_score and medium_score > 0:
        best = "Medium"
    elif low_score > 0:
        best = "Low"
    else:
        best = "Unmatched"
    return total, best


async def fetch_sitemap_urls(client: httpx.AsyncClient, sitemap_url: str) -> list[tuple[str, Optional[str]]]:
    """Fetch sitemap and return (url, lastmod) list. Follows sitemap index recursively."""
    resp = await client.get(sitemap_url, timeout=30.0)
    resp.raise_for_status()
    content = resp.text
    if not content.strip():
        raise ValueError("Sitemap returned empty content")

    items, is_index = _extract_urls_from_xml(content)

    if is_index:
        all_urls: list[tuple[str, Optional[str]]] = []
        for child_sitemap_url, _ in items:
            try:
                sub = await fetch_sitemap_urls(client, child_sitemap_url)
                all_urls.extend(sub)
            except Exception:
                continue
        return all_urls

    return items


async def prioritize_sitemap(sitemap_url: str, keywords: KeywordPriorities) -> list[UrlResult]:
    """Fetch sitemap, score all URLs, sort by score descending."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        url_list = await fetch_sitemap_urls(client, sitemap_url)

    if not url_list:
        return []

    results: list[UrlResult] = []
    for url, lastmod in url_list:
        parsed = urlparse(url)
        path = (parsed.path or "").lower()
        score, category = _score_url(path, keywords)
        depth = _url_depth(url)
        results.append(
            UrlResult(
                url=url,
                matched_category=category,
                priority_score=score,
                url_depth=depth,
                last_modified=lastmod,
            )
        )

    results.sort(key=lambda r: (-r.priority_score, -r.url_depth))
    return results
