import * as React from "react"
import { Line, LineChart, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip } from "recharts"
import { fmtPct, shortLabel } from "../data"
import type { SiteData } from "../data"

/** Bump-chart style ranking flow across all measured configurations. */
export function Rankings({ site, goCompare }: { site: SiteData; goCompare: (key: string) => void }) {
  const models = site.models.map((m) => m.model_id)
  const labels = Object.fromEntries(site.models.map((m) => [m.model_id, shortLabel(m.model_id)]))
  return (
    <div>
      <h2>Ranking stability</h2>
      <p className="note">
        One row per measured configuration; cell value is the model's rank (1 = best).
        Rows and columns come from the export — no configuration is hand-picked.
      </p>
      <div className="table-wrap">
        <table className="data" aria-label="Model rank by configuration">
          <thead><tr><th>Configuration</th>{models.map((m) => <th key={m}>{labels[m]}</th>)}<th></th></tr></thead>
          <tbody>
            {site.rankings.map((r) => (
              <tr key={r.config_key}>
                <td><code>{r.config_key}</code></td>
                {models.map((m) => {
                  const mem = r.ranking.find((x) => x.model_id === m)
                  return <td key={m} className="num">{mem ? <strong>{mem.rank}</strong> : <span className="note">—</span>}</td>
                })}
                <td>{r.config_key !== "control=control" && <button className="copybtn" type="button" onClick={() => goCompare(r.config_key)}>Compare</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Control vs variant</h3>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Variant</th><th>τ vs control</th><th>Reversals</th><th>Ranking</th></tr></thead>
          <tbody>
            {site.ranking_comparisons.map((c) => (
              <tr key={c.variant_key}>
                <td><code>{c.variant_key}</code></td>
                <td className="num">{c.tau !== null ? c.tau.toFixed(2) : "n/a"}</td>
                <td className="num">{c.n_reversals}</td>
                <td>{c.reordered ? <strong>changed</strong> : "preserved"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <RankChart site={site} />
    </div>
  )
}

function RankChart({ site }: { site: SiteData }) {
  const cfgs = site.rankings.filter((r) => r.n_models >= 2).slice(0, 8)
  const models = [...new Set(cfgs.flatMap((r) => r.ranking.map((m) => m.model_label)))]
  const data = cfgs.map((r) => {
    const row: Record<string, string | number> = { config: r.config_key.replace("=", " ") }
    for (const m of r.ranking) row[m.model_label] = m.rank
    return row
  })
  const colors = ["#0b3d91", "#a4262c", "#1e6b3a", "#8a5a00"]
  return (
    <section aria-label="Rank flow chart">
      <h3>Rank flow (lower is better)</h3>
      <div style={{ width: "100%", height: 300 }} role="img" aria-label={`Rank of ${models.join(", ")} across ${cfgs.length} configurations`}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 40, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="config" angle={-25} textAnchor="end" height={70} tick={{ fontSize: 11 }} />
            <YAxis reversed domain={[1, Math.max(1, models.length)]} ticks={models.map((_, i) => i + 1)} tick={{ fontSize: 11 }} />
            <Tooltip />
            {models.map((m, i) => (
              <Line key={m} type="monotone" dataKey={m} stroke={colors[i % colors.length]} strokeWidth={2} dot connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
