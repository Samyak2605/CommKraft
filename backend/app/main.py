import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.routers import sitemap

app = FastAPI(
    title="Intelligent Sitemap Prioritizer",
    description="Rank sitemap URLs by relevance to prioritized keywords.",
    version="1.0.0",
)

# CORS: allow frontend origin and common patterns for Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sitemap.router)

# Serve static frontend (for production build)
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir() and (static_dir / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/{path:path}")
    def catch_all(path: str):
        """Serve index.html for client-side routing."""
        if path.startswith("api") or path.startswith("assets"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        fp = static_dir / path
        if fp.is_file():
            return FileResponse(fp)
        return FileResponse(static_dir / "index.html")
else:
    @app.get("/")
    def index():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            "<p>Intelligent Sitemap Prioritizer API is running. "
            "Build the frontend (<code>cd frontend && npm run build</code>) and restart to serve the UI, "
            "or use <a href='/docs'>/docs</a> for the API.</p>"
        )
