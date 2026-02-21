import re
from urllib.parse import urlparse
from typing import Optional

import httpx
import numpy as np
from defusedxml import ElementTree as ET

from app.models import KeywordPriorities, UrlResult

# Lazy-loaded spaCy NLP model for semantic similarity (e.g. health ~ wellness)
_nlp = None
# Lazy-loaded sentence-transformers model for phrase-level embeddings
_embed_model = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_md")
        except Exception:
            _nlp = False  # mark as unavailable
    return _nlp if _nlp else None


def _get_embed_model():
    """Load sentence-transformers model for phrase-level embeddings (health/wellness same rank)."""
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embed_model = False
    return _embed_model if _embed_model else None


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


def _path_terms(path_lower: str) -> list[str]:
    """Extract tokens from URL path (split by / and -). Used for NLP similarity."""
    if not path_lower:
        return []
    parts = re.split(r"[/\-_.]+", path_lower)
    return [p for p in parts if len(p) > 1]


def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))


def _keyword_vectors(nlp, keyword_list: list[str]) -> list[np.ndarray]:
    """Get one vector per keyword (average of token vectors for multi-word)."""
    vectors = []
    for k in keyword_list:
        doc = nlp(k.lower().strip())
        if not doc:
            continue
        vecs = [t.vector for t in doc if t.has_vector]
        if not vecs:
            continue
        vectors.append(np.mean(vecs, axis=0))
    return vectors


def _score_url_nlp(
    path_lower: str,
    keywords: KeywordPriorities,
    nlp,
    term_vectors: dict[str, np.ndarray],
    kw_high: list[np.ndarray],
    kw_medium: list[np.ndarray],
    kw_low: list[np.ndarray],
) -> tuple[float, str]:
    """
    Score URL by semantic similarity. Terms like 'health' and 'wellness' get similar
    scores so they rank together. Weights: High=3, Medium=2, Low=1.
    """
    terms = _path_terms(path_lower)
    if not terms:
        return 0.0, "Unmatched"

    def max_sim(term_vecs: list[np.ndarray], kw_vecs: list[np.ndarray]) -> float:
        if not kw_vecs:
            return 0.0
        best = 0.0
        for tvec in term_vecs:
            for kvec in kw_vecs:
                sim = _cosine_similarity(tvec, kvec)
                if sim > best:
                    best = sim
        return best

    def exact_match_sim(tier_keywords: list[str]) -> float:
        for k in tier_keywords:
            if k in path_lower:
                return 1.0
        return 0.0

    term_vecs = []
    for t in terms:
        if t in term_vectors:
            term_vecs.append(term_vectors[t])
        else:
            doc = nlp(t)
            v = getattr(doc, "vector", None)
            if v is not None and np.linalg.norm(v) > 0:
                term_vecs.append(v)
                term_vectors[t] = v

    # Use similarity; fallback to 1.0 for exact match if keyword in path
    high_sim = max(max_sim(term_vecs, kw_high) if kw_high else 0.0, exact_match_sim(keywords.High))
    med_sim = max(max_sim(term_vecs, kw_medium) if kw_medium else 0.0, exact_match_sim(keywords.Medium))
    low_sim = max(max_sim(term_vecs, kw_low) if kw_low else 0.0, exact_match_sim(keywords.Low))

    # Weighted score: same rank for semantically similar terms (e.g. health ≈ wellness)
    weighted_high = 3.0 * high_sim
    weighted_med = 2.0 * med_sim
    weighted_low = 1.0 * low_sim
    total = weighted_high + weighted_med + weighted_low

    if total <= 0:
        return 0.0, "Unmatched"
    if weighted_high >= weighted_med and weighted_high >= weighted_low:
        best = "High"
    elif weighted_med >= weighted_low:
        best = "Medium"
    else:
        best = "Low"
    return round(total, 4), best


def _path_to_sentence(path_lower: str) -> str:
    """Turn URL path into a phrase for embedding (e.g. /blog/health-news -> blog health news)."""
    if not path_lower:
        return ""
    return " ".join(re.split(r"[/\-_.]+", path_lower)).strip()


def _score_url_embed(
    path_embed: np.ndarray,
    high_embs: np.ndarray,
    med_embs: np.ndarray,
    low_embs: np.ndarray,
) -> tuple[float, str]:
    """
    Score one URL path using its embedding vs keyword embeddings. Same rank for
    semantically similar phrases (e.g. health / wellness). Weights: High=3, Medium=2, Low=1.
    """
    def max_cos(v: np.ndarray, pool: np.ndarray) -> float:
        if pool is None or (hasattr(pool, "shape") and (len(pool) == 0 or pool.size == 0)):
            return 0.0
        sims = np.dot(pool, v) / (np.linalg.norm(pool, axis=1) * np.linalg.norm(v) + 1e-9)
        return float(np.max(sims).item())

    high_sim = max_cos(path_embed, high_embs)
    med_sim = max_cos(path_embed, med_embs)
    low_sim = max_cos(path_embed, low_embs)
    w_high = 3.0 * high_sim
    w_med = 2.0 * med_sim
    w_low = 1.0 * low_sim
    total = w_high + w_med + w_low
    if total <= 0:
        return 0.0, "Unmatched"
    if w_high >= w_med and w_high >= w_low:
        best = "High"
    elif w_med >= w_low:
        best = "Medium"
    else:
        best = "Low"
    return round(total, 4), best


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
    """Fetch sitemap, score by embeddings (preferred) or spaCy or exact match, sort descending."""
    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        url_list = await fetch_sitemap_urls(client, sitemap_url)

    if not url_list:
        return []

    path_by_url = [(url, lastmod, (urlparse(url).path or "").lower()) for url, lastmod in url_list]
    paths = [p for _, _, p in path_by_url]
    path_sentences = [_path_to_sentence(p) for p in paths]

    # 1) Prefer sentence-transformers (phrase-level embeddings)
    embed_model = _get_embed_model()
    if embed_model is not None:
        path_embs = embed_model.encode(
            [s or " " for s in path_sentences],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        high_list = [k.strip().lower() for k in keywords.High if k.strip()]
        med_list = [k.strip().lower() for k in keywords.Medium if k.strip()]
        low_list = [k.strip().lower() for k in keywords.Low if k.strip()]
        high_embs = embed_model.encode(high_list, normalize_embeddings=True) if high_list else np.zeros((0, path_embs.shape[1]))
        med_embs = embed_model.encode(med_list, normalize_embeddings=True) if med_list else np.zeros((0, path_embs.shape[1]))
        low_embs = embed_model.encode(low_list, normalize_embeddings=True) if low_list else np.zeros((0, path_embs.shape[1]))
        use_embed = high_embs.shape[0] or med_embs.shape[0] or low_embs.shape[0]
    else:
        use_embed = False
        path_embs = high_embs = med_embs = low_embs = None

    # 2) Fallback: spaCy word vectors
    nlp = _get_nlp() if not use_embed else None
    if nlp is not None and not use_embed:
        kw_high = _keyword_vectors(nlp, keywords.High)
        kw_medium = _keyword_vectors(nlp, keywords.Medium)
        kw_low = _keyword_vectors(nlp, keywords.Low)
        all_terms = set()
        for _, _, path in path_by_url:
            all_terms.update(_path_terms(path))
        term_vectors = {}
        terms_list = list(all_terms)
        for term, doc in zip(terms_list, nlp.pipe(terms_list)):
            v = getattr(doc, "vector", None)
            if v is not None and np.linalg.norm(v) > 0:
                term_vectors[term] = v.copy()
        use_nlp = kw_high or kw_medium or kw_low
    else:
        term_vectors = {}
        kw_high = kw_medium = kw_low = []
        use_nlp = False

    results: list[UrlResult] = []
    for i, (url, lastmod, path) in enumerate(path_by_url):
        if use_embed:
            score, category = _score_url_embed(
                path_embs[i], high_embs, med_embs, low_embs
            )
        elif use_nlp:
            score, category = _score_url_nlp(
                path, keywords, nlp, term_vectors, kw_high, kw_medium, kw_low
            )
        else:
            s, category = _score_url(path, keywords)
            score = float(s)
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
