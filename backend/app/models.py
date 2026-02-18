from typing import Optional
from pydantic import BaseModel, Field


class KeywordPriorities(BaseModel):
    High: list[str] = Field(default_factory=list, description="High priority keywords")
    Medium: list[str] = Field(default_factory=list, description="Medium priority keywords")
    Low: list[str] = Field(default_factory=list, description="Low priority keywords")


class SitemapRequest(BaseModel):
    sitemap_url: str = Field(..., description="URL of the sitemap XML")
    keywords: KeywordPriorities = Field(
        ...,
        example={
            "High": ["cardiology", "emergency", "surgery"],
            "Medium": ["doctors", "appointments"],
            "Low": ["blog", "news"],
        },
    )


class UrlResult(BaseModel):
    url: str
    matched_category: str
    priority_score: int
    url_depth: int
    last_modified: Optional[str] = None


class SitemapResponse(BaseModel):
    total_urls: int
    results: list[UrlResult]
    error: Optional[str] = None
