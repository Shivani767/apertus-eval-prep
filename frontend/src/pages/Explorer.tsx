import * as React from "react"
import { StatusBadge } from "../components"
import { shortLabel } from "../data"
import { filtersFromHash } from "./chrome"
import type { SiteData } from "../data"

/** Filterable experiment explorer with URL-shareable filters. */
export function Explorer({ site, goCell }: { site: SiteData; goCell: (runId: string) => void }) {
  const initial = React.useMemo(filtersFromHash, [])
  const [model, setModel] = React.useState(initial.model ?? "")
  const [factor, setFactor] = React.useState(initial.factor ?? "")
  const [status, setStatus] = React.useState(initial.status ?? "")
  const [query, setQuery] = React.useState(initial.q ?? "")

  const models = React.useMemo(() => [...new Set(site.cells.map((c) => c.model_id))].sort(), [site])
  const factors = React.useMemo(() => [...new Set(site.cells.map((c) => c.factor))].sort(), [site])

  const rows = site.cells.filter((c) =>
    (!model || c.model_id === model) &&
    (!factor || c.factor === factor) &&
    (!status || c.status === status) &&
    (!query || c.run_id.toLowerCase().includes(query.toLowerCase()) ||
      c.config_key.toLowerCase().includes(query.toLowerCase())))

  React.useEffect(() => {
    const p = new URLSearchParams()
    if (model) p.set("model", model)
    if (factor) p.set("factor", factor)
    if (status) p.set("status", status)
    if (query) p.set("q", query)
    const q = p.toString()
    window.location.hash = `#/explorer${q ? `?${q}` : ""}`
  }, [model, factor, status, query])

  return (
    <div>
      <h2>Experiment explorer</h2>
      <p className="note">{rows.length} of {site.cells.length} cells · filters are URL-shareable.</p>
      <div className="filters" role="search">
        <label>Model
          <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="Filter by model">
            <option value="">All models</option>
            {models.map((m) => <option key={m} value={m}>{shortLabel(m)}</option>)}
          </select>
        </label>
        <label>Factor
          <select value={factor} onChange={(e) => setFactor(e.target.value)} aria-label="Filter by factor">
            <option value="">All factors</option>
            {factors.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
        <label>Status
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
            <option value="">Any status</option>
            <option value="MEASURED">MEASURED</option>
            <option value="SAMPLED">SAMPLED</option>
            <option value="PENDING">PENDING</option>
          </select>
        </label>
        <label>Search
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="run id or config…" aria-label="Search runs" />
        </label>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Model</th><th>Configuration</th><th>Score</th><th>n</th><th>Status</th><th>Detail</th></tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.run_id}>
                <td>{shortLabel(c.model_id)}</td>
                <td><code>{c.config_key}</code></td>
                <td className="num">{c.accuracy !== null ? `${(c.accuracy * 100).toFixed(2)}%` : "Not measured"}</td>
                <td className="num">{c.n ?? "—"}</td>
                <td><StatusBadge status={c.status} /></td>
                <td><button className="copybtn" type="button" onClick={() => goCell(c.run_id)}>Open</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
