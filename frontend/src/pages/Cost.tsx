import { Scatter, ScatterChart, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip, ZAxis } from "recharts"
import { Delta } from "../components"
import { fmtPct, shortLabel } from "../data"
import type { SiteData } from "../data"

/** Backend / quantization / cost+Pareto: performance vs score, kept separate. */
export function Cost({ site }: { site: SiteData }) {
  const p = site.pareto
  const pts = [...p.frontier, ...p.dominated].filter((x) => x.latency_ms !== null && x.accuracy !== null)
  const data = pts.map((x) => ({ x: x.latency_ms, y: x.accuracy, label: `${x.model_label} / ${x.config_key}`, frontier: x.pareto === "frontier" }))
  return (
    <div>
      <h2>Backend, quantization &amp; cost</h2>
      <p className="note">
        Faster inference is a <strong>performance</strong> change, not a capability change —
        it is shown separately from <strong>evaluation-score</strong> effects below.
        Pareto frontier: lowest latency at each accuracy level (measured latencies only;
        cells without measured latency are excluded, never zeroed).
      </p>
      <h3>Accuracy vs latency</h3>
      <div style={{ width: "100%", height: 320 }} role="img" aria-label="Accuracy versus latency scatter">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" dataKey="x" name="latency" unit=" ms" tick={{ fontSize: 11 }} label={{ value: "mean latency (ms)", position: "bottom", fontSize: 12 }} />
            <YAxis type="number" dataKey="y" name="accuracy" domain={["auto", "auto"]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
            <ZAxis type="number" range={[60, 60]} />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v, name) => [name === "accuracy" ? fmtPct(Number(v)) : `${v} ms`, String(name)]} labelFormatter={() => ""} />
            <Scatter name="dominated" data={data.filter((d) => !d.frontier)} fill="#8a93a0" />
            <Scatter name="frontier" data={data.filter((d) => d.frontier)} fill="#0b3d91" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Cell</th><th>Latency</th><th>Throughput</th><th>Score</th><th>Pareto</th></tr></thead>
        <tbody>
          {[...p.frontier, ...p.dominated, ...p.excluded].map((x) => (
            <tr key={x.label}>
              <td><code>{x.label}</code></td>
              <td className="num">{x.latency_ms !== null ? `${x.latency_ms.toFixed(0)} ms` : "Unavailable"}</td>
              <td className="num">{x.tts !== null && x.tts !== undefined ? `${Number(x.tts).toFixed(1)} tok/s` : "Unavailable"}</td>
              <td className="num">{fmtPct(x.accuracy)}</td>
              <td>{x.pareto}</td>
            </tr>
          ))}
        </tbody>
      </table></div>

      <h3>Score effects: backend &amp; quantization</h3>
      <p className="note">Paired per-item effects of runtime choices on the measured score.</p>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Model</th><th>Change</th><th>Δ score</th><th>95% CI</th><th>p (BH)</th></tr></thead>
        <tbody>
          {site.statistics.comparisons
            .filter((c) => c.factor === "backend" || c.factor === "quantization")
            .map((c) => (
              <tr key={`${c.model_id} ${c.variant_key}`}>
                <td>{shortLabel(c.model_id)}</td>
                <td><code>{c.variant_key}</code></td>
                <td><Delta x={c.delta} /></td>
                <td className="num">[{c.delta_ci95[0] !== null ? fmtPct(c.delta_ci95[0]) : "?"} – {c.delta_ci95[1] !== null ? fmtPct(c.delta_ci95[1]) : "?"}]</td>
                <td className="num">{c.perm_p_bh !== null ? (c.perm_p_bh < 0.001 ? "<0.001" : c.perm_p_bh.toFixed(3)) : "n/a"}</td>
              </tr>
            ))}
        </tbody>
      </table></div>
    </div>
  )
}
