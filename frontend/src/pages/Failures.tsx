import * as React from "react"
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { shortLabel } from "../data"
import type { SiteData } from "../data"

const CATS = ["correct", "wrong_answer", "unparseable", "empty_output", "runtime_error"] as const

/** Failure taxonomy: benchmark evaluation is more than one accuracy number. */
export function Failures({ site }: { site: SiteData }) {
  const [config, setConfig] = React.useState("control=control")
  const cfgs = React.useMemo(() => [...new Set(site.failures.map((f) => f.config_key))].sort(), [site])
  const rows = site.failures.filter((f) => f.config_key === config)
  const chartData = rows.map((f) => ({
    name: shortLabel(f.model_id),
    ...Object.fromEntries(CATS.map((c) => [c, f.total ? ((f.counts[c] ?? 0) / f.total) * 100 : 0])),
  }))
  const colors: Record<string, string> = {
    correct: "#1e6b3a", wrong_answer: "#a4262c", unparseable: "#8a5a00",
    empty_output: "#5b6470", runtime_error: "#0b3d91",
  }
  return (
    <div>
      <h2>Failure analysis</h2>
      <p className="note">
        Mutually exclusive per-item categories from measured run artifacts. A zero is a
        measured zero, not a missing value. Goal: show evaluation is more than one aggregate number.
      </p>
      <div className="filters">
        <label>Configuration
          <select value={config} onChange={(e) => setConfig(e.target.value)} aria-label="Failure configuration">
            {cfgs.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      </div>
      <div style={{ width: "100%", height: 280 }} role="img" aria-label={`Failure category share per model under ${config}`}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip formatter={(v) => [`${Number(v).toFixed(1)}%`, "share"]} />
            {CATS.map((c) => <Bar key={c} dataKey={c} stackId="a" fill={colors[c]} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Model</th><th>Items</th><th>Failure rate</th>{CATS.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.run_id}>
                <td>{shortLabel(f.model_id)}</td>
                <td className="num">{f.total}</td>
                <td className="num">{f.failure_rate !== null ? `${(f.failure_rate * 100).toFixed(2)}%` : "Not measured"}</td>
                {CATS.map((c) => <td key={c} className="num">{f.counts[c] ?? 0}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3>Per-task breakdown</h3>
      {rows.map((f) => (
        <div key={f.run_id}>
          <h4 className="note" style={{ color: "var(--ink)" }}>{shortLabel(f.model_id)}</h4>
          <div className="table-wrap"><table className="data">
            <thead><tr><th>Task</th><th>Total</th>{CATS.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>
              {Object.entries(f.per_task).map(([t, b]) => (
                <tr key={t}><td><code>{t}</code></td><td className="num">{b.total}</td>
                  {CATS.map((c) => <td key={c} className="num">{(b as Record<string, number>)[c] ?? 0}</td>)}</tr>
              ))}
            </tbody>
          </table></div>
        </div>
      ))}
    </div>
  )
}
