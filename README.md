# Intelligent Sitemap Prioritizer

Full-stack application that accepts a website's sitemap URL and a set of prioritized keywords, then ranks URLs by relevance. Built for deployment on [Render.com](https://render.com).

**Live demo:** [https://sitemap-prioritizer.onrender.com](https://sitemap-prioritizer.onrender.com)

## Tech Stack

- **Backend:** Python FastAPI (async sitemap fetching, defusedxml parsing)
- **Frontend:** React (Vite), minimal modern UI
- **Deployment:** Render.com (single Web Service)

## Features

- **Input:** Sitemap XML URL + keywords by priority (High / Medium / Low)
- **Scoring:** High = 3 pts, Medium = 2 pts, Low = 1 pt per keyword match in URL path; best category assigned
- **Output:** Table of URL, Matched Category, Priority Score, URL depth, Last modified (when present in sitemap)
- Handles **1,000+ URLs** (async fetch, efficient parsing, paginated table)
- CORS enabled; error handling for invalid sitemap; loading state in UI

## Project Structure

```
sitemap-prioritizer/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, static serve
│   │   ├── models.py        # Pydantic models
│   │   ├── routers/
│   │   │   └── sitemap.py   # POST /api/prioritize
│   │   └── services/
│   │       └── sitemap_service.py  # Fetch, parse, score
│   ├── requirements.txt
│   └── static/              # Frontend build output (generated)
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── render.yaml
└── README.md
```

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (with API proxy to backend)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the backend.

### Production build (local test)

```bash
cd frontend && npm ci && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then open http://localhost:8000.


## API

- **POST /api/prioritize**  
  **Body (JSON):**
  ```json
  {
    "sitemap_url": "https://example.com/sitemap.xml",
    "keywords": {
      "High": ["cardiology", "emergency", "surgery"],
      "Medium": ["doctors", "appointments"],
      "Low": ["blog", "news"]
    }
  }
  ```
  **Response:** `{ "total_urls": number, "results": [ { "url", "matched_category", "priority_score", "url_depth", "last_modified" }, ... ] }`


- [x] CORS setup  
- [x] Error handling for invalid sitemap  
- [x] Loading state in frontend  
- [x] Clean modern UI  
- [x] Handles 1,000+ URLs (async + pagination)
