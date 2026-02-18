import logging

from fastapi import APIRouter, HTTPException
from httpx import HTTPStatusError, RequestError

from app.models import SitemapRequest, SitemapResponse, UrlResult
from app.services.sitemap_service import prioritize_sitemap

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["sitemap"])


@router.post("/prioritize", response_model=SitemapResponse)
async def prioritize(request: SitemapRequest):
    """Fetch sitemap, score URLs by keyword relevance, return sorted list."""
    sitemap_url = (request.sitemap_url or "").strip()
    if not sitemap_url:
        raise HTTPException(status_code=400, detail="sitemap_url is required")
    if not sitemap_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="sitemap_url must be a valid HTTP(S) URL")

    try:
        results: list[UrlResult] = await prioritize_sitemap(sitemap_url, request.keywords)
    except RequestError as e:
        logger.exception("Request error fetching sitemap")
        raise HTTPException(
            status_code=422,
            detail=f"Could not fetch sitemap: {str(e)}. Check the URL and try again.",
        )
    except HTTPStatusError as e:
        logger.exception("HTTP error fetching sitemap")
        raise HTTPException(
            status_code=422,
            detail=f"Sitemap returned error {e.response.status_code}. Invalid or inaccessible sitemap.",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error parsing sitemap")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sitemap or parsing error: {str(e)}",
        )

    return SitemapResponse(total_urls=len(results), results=results)
