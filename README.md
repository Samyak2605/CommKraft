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

## Deploy on Render.com

### Option A: Connect repo and use Blueprint (recommended)

1. Push this project to a **GitHub** (or GitLab) repository.
2. Log in to [Render](https://render.com) and go to **Dashboard** → **New** → **Blueprint**.
3. Connect the repository and select the repo that contains `render.yaml`.
4. Render will detect `render.yaml` and create a **Web Service** with:
   - **Build:** `pip install -r backend/requirements.txt` then `cd frontend && npm ci && npm run build`
   - **Start:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set **Root Directory** to the directory that contains `backend/`, `frontend/`, and `render.yaml` (usually `.` or leave blank if the repo root is this folder).
6. Click **Apply** and wait for the first deploy. Your app URL will be like `https://sitemap-prioritizer-xxxx.onrender.com`.

**Root Directory:** If your repo root is the folder that contains `backend/`, `frontend/`, and `render.yaml`, leave **Root Directory** blank. If this app lives in a subfolder (e.g. `sitemap-prioritizer/`), set **Root Directory** to that folder name.

### Option B: Manual Web Service (no Blueprint)

1. Push the code to GitHub (or GitLab).
2. In Render: **Dashboard** → **New** → **Web Service**.
3. Connect your repository.
4. Configure:
   - **Name:** `sitemap-prioritizer` (or any name).
   - **Region:** Oregon (or your choice).
   - **Branch:** `main` (or your default branch).
   - **Root Directory:** Leave blank if the repo root contains `backend/` and `frontend/`. Otherwise set it to the folder that contains them (e.g. `sitemap-prioritizer` if the repo root is the parent).
   - **Runtime:** **Python 3**.
   - **Build Command:**
     ```bash
     pip install -r backend/requirements.txt
     cd frontend && npm ci && npm run build
     ```
   - **Start Command:**
     ```bash
     cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Plan:** Free (or paid).
5. Click **Create Web Service**. Render will build and deploy. Use the generated URL (e.g. `https://sitemap-prioritizer-xxxx.onrender.com`) to access the UI.

### Option C: Deploy with Docker (Node + Python in one image)

If the default Render Python environment does not have Node.js for the frontend build, use Docker:

1. **New** → **Web Service** → connect repo.
2. Set **Environment** to **Docker**.
3. Leave **Dockerfile path** as `Dockerfile` (or set to `sitemap-prioritizer/Dockerfile` if your root is the parent).
4. **Root Directory:** same as above (folder containing `backend/`, `frontend/`, `Dockerfile`).
5. Create Web Service. Render will build the Docker image (Node builds frontend, Python serves app) and run it.

### Notes for Render

- **Free tier:** The service may spin down after inactivity; the first request after idle can be slow (cold start).
- **Environment:** Render sets `PORT` automatically; no need to add it.
- If your repo root is **not** the folder that contains `backend/` and `frontend/`, set **Root Directory** to that folder (e.g. `sitemap-prioritizer`).
- If the default build fails (e.g. `npm: command not found`), use **Option C (Docker)** so both Node and Python are available in the build.

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

## Deliverables

- [x] Clean project structure  
- [x] `requirements.txt`  
- [x] README with deployment instructions  
- [x] Render deployment config (`render.yaml`)  
- [x] CORS setup  
- [x] Error handling for invalid sitemap  
- [x] Loading state in frontend  
- [x] Clean modern UI  
- [x] Handles 1,000+ URLs (async + pagination)
