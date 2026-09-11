import * as React from "react"
import { Delta } from "../components"
import { fmtPct } from "../data"
import type { SiteData } from "../data"

/** Sortable/filterable results matrix; row click opens the cell detail. */
export function Matrix({ site, goCell }: { site: SiteData; goCell: (runId: string) => void }) {
  const [model, setModel] = React.useState("")
  const [q, setQ] = React.useState("")
  const [sortKey, setSortKey] = React.useState<"accuracy" | "config_key" | "model_id">("accuracy")
  const [desc, setDesc] = React.useState(true)

  const rows = React.useMemo(() => {
    const r = site.cells.filter((c) =>
      (!model || c.model_id === model) &&
      (!q || c.run_id.toLowerCase().includes(q.toLowerCase()) ||
        c.config_key.toLowerCase().includes(q.toLowerCase())))
    const val = (c: (typeof r)[number]) =>
      sortKey === "accuracy" ? (c.accuracy ?? -1) : sortKey === "config_key" ? c.config_key : c.model_id
    return [...r].sort((a, b) => {
      const va = val(a), vb = val(b)
      const cmp = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb))
      return desc ? -cmp : cmp
    })
  }, [site, model, q, sortKey, desc])

  const rankOf = (runId: string) => {
    const cell = site.cells.find((c) => c.run_id === runId)
    if (!cell) return "—"
    const r = site.rankings.find((x) => x.config_key === cell.config_key)
    return r?.ranking.find((m) => m.model_id === cell.model_id)?.rank ?? "—"
  }

  return (
    <div>
      <h2>Results matrix</h2>
      <div className="filters">
        <label>Model
          <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="Filter by model">
            <option value="">All</option>
            {site.models.map((m) => <option key={m.model_id} value={m.model_id}>{m.label}</option>)}
          </select>
        </label>
        <label>Search
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="run id or config…" aria-label="Search matrix" />
        </label>
        <label>Sort by
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as typeof sortKey)} aria-label="Sort column">
            <option value="accuracy">Score</option>
            <option value="config_key">Configuration</option>
            <option value="model_id">Model</option>
          </select>
        </label>
        <button className="copybtn" type="button" onClick={() => setDesc(!desc)} aria-label="Toggle sort direction">
          {desc ? "↓ desc" : "↑ asc"}
        </button>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Model</th><th>Configuration</th><th>Score</th><th>Δ vs control</th><th>Rank in config</th><th>Evidence</th></tr></thead>
          <tbody>
            {rows.map((c) => {
              const st = site.statistics.comparisons.find((s) => s.variant_key === c.config_key && s.model_id === c.model_id)
              return (
                <tr key={c.run_id} onClick={() => c.accuracy !== null && goCell(c.run_id)} style={c.accuracy !== null ? { cursor: "pointer" } : undefined}>
                  <td>{c.model_label}</td>
                  <td><code>{c.config_key}</code></td>
                  <td className="num">{fmtPct(c.accuracy)}</td>
                  <td>{c.factor === "control" ? "—" : <Delta x={st?.delta} />}</td>
                  <td className="num">{rankOf(c.run_id)}</td>
                  <td className="note">{st ? `p(BH)=${st.perm_p_bh !== null ? (st.perm_p_bh < 0.001 ? "<0.001" : st.perm_p_bh.toFixed(3)) : "n/a"}` : "descriptive"}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="note">Click a measured row to open the experiment detail. Δ and p-values come from the paired per-item analysis on the Statistics page.</p>
    </div>
  )
}
