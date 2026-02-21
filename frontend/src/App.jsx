import { useState, useCallback } from 'react'
import './App.css'

const DEFAULT_KEYWORDS = {
  High: ['cardiology', 'emergency', 'surgery'],
  Medium: ['doctors', 'appointments'],
  Low: ['blog', 'news'],
}

function getApiBase() {
  return ''
}

export default function App() {
  const [sitemapUrl, setSitemapUrl] = useState('')
  const [keywords, setKeywords] = useState(DEFAULT_KEYWORDS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)

  const updateKeywordList = useCallback((level, value) => {
    const list = (value || '')
      .split(/[\n,]+/)
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean)
    setKeywords((k) => ({ ...k, [level]: list }))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setData(null)
    if (!sitemapUrl.trim()) {
      setError('Please enter a sitemap URL.')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${getApiBase()}/api/prioritize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sitemap_url: sitemapUrl.trim(),
          keywords: {
            High: keywords.High,
            Medium: keywords.Medium,
            Low: keywords.Low,
          },
        }),
      })
      const json = await res.json().catch(() => ({}))
      if (!res.ok) {
        const d = json.detail
        const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x.loc?.join('.')).filter(Boolean).join(', ') : 'Request failed'
        setError(msg || `Error ${res.status}`)
        return
      }
      setData(json)
      setPage(0)
    } catch (err) {
      setError(err.message || 'Network error. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const categoryClass = (cat) => {
    if (cat === 'High') return 'badge-high'
    if (cat === 'Medium') return 'badge-medium'
    if (cat === 'Low') return 'badge-low'
    return 'badge-unmatched'
  }

  const PAGE_SIZE = 100
  const [page, setPage] = useState(0)
  const results = data?.results ?? []
  const totalPages = Math.ceil(results.length / PAGE_SIZE) || 1
  const pageResults = results.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const goToPage = (p) => setPage(Math.max(0, Math.min(p, totalPages - 1)))

  return (
    <div className="app">
      <header className="header">
        <h1>Intelligent Sitemap Prioritizer</h1>
        <p className="subtitle">Rank sitemap URLs by relevance to your business priorities</p>
      </header>

      <main className="main">
        <form onSubmit={handleSubmit} className="card form-card">
          <div className="form-group">
            <label htmlFor="sitemap">Sitemap URL</label>
            <input
              id="sitemap"
              type="url"
              placeholder="https://www.sitemaps.org/sitemap.xml"
              value={sitemapUrl}
              onChange={(e) => setSitemapUrl(e.target.value)}
              disabled={loading}
              className="input"
            />
          </div>

          <div className="keywords-section">
            <label>Keywords by priority</label>
            <p className="hint">Comma or newline separated. NLP: similar terms (e.g. health, wellness) rank together. High = 3×, Medium = 2×, Low = 1×.</p>
            <div className="keywords-grid">
              {['High', 'Medium', 'Low'].map((level) => (
                <div key={level} className="keyword-group">
                  <span className={`keyword-label keyword-${level.toLowerCase()}`}>{level}</span>
                  <textarea
                    rows={3}
                    value={keywords[level].join(', ')}
                    onChange={(e) => updateKeywordList(level, e.target.value)}
                    disabled={loading}
                    placeholder={level === 'High' ? 'e.g. cardiology, emergency' : level === 'Medium' ? 'e.g. doctors, appointments' : 'e.g. blog, news'}
                    className="input keyword-input"
                  />
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner" aria-hidden />
                Analyzing sitemap…
              </>
            ) : (
              'Prioritize URLs'
            )}
          </button>
        </form>

        {data && (
          <div className="card results-card">
            <h2>Results ({data.total_urls} URLs)</h2>
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  type="button"
                  className="btn-page"
                  onClick={() => goToPage(page - 1)}
                  disabled={page === 0}
                >
                  Previous
                </button>
                <span className="page-info">
                  Page {page + 1} of {totalPages} ({page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, results.length)} of {results.length})
                </span>
                <button
                  type="button"
                  className="btn-page"
                  onClick={() => goToPage(page + 1)}
                  disabled={page >= totalPages - 1}
                >
                  Next
                </button>
              </div>
            )}
            <div className="table-wrap">
              <table className="results-table">
                <thead>
                  <tr>
                    <th>URL</th>
                    <th>Category</th>
                    <th>Score</th>
                    <th>Depth</th>
                    <th>Last modified</th>
                  </tr>
                </thead>
                <tbody>
                  {pageResults.map((row, i) => (
                    <tr key={page * PAGE_SIZE + i}>
                      <td className="url-cell">
                        <a href={row.url} target="_blank" rel="noopener noreferrer" className="url-link">
                          {row.url}
                        </a>
                      </td>
                      <td>
                        <span className={`badge ${categoryClass(row.matched_category)}`}>
                          {row.matched_category}
                        </span>
                      </td>
                      <td className="score-cell">{Number(row.priority_score) === row.priority_score && row.priority_score % 1 !== 0 ? row.priority_score.toFixed(2) : row.priority_score}</td>
                      <td>{row.url_depth}</td>
                      <td className="mono muted">{row.last_modified || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Deployable on Render · FastAPI + React</p>
      </footer>
    </div>
  )
}
