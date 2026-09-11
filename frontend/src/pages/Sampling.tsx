import { fmtPct, shortLabel } from "../data"
import type { SiteData } from "../data"

/** Sampling stability across seeds (T=0.7 arm). */
export function Sampling({ site }: { site: SiteData }) {
  const sampled = site.cells.filter((c) => c.factor === "sampled" && c.accuracy !== null)
  const byModel = [...new Set(sampled.map((c) => c.model_id))].sort()
  return (
    <div>
      <h2>Sampling stability</h2>
      <p className="note">
        Same configuration, different seeds, at temperature 0.7. Conclusions are stable
        only if the seed spread is small relative to the gaps between models.
      </p>
      {byModel.length === 0 && <p className="note">No sampled cells in the current export.</p>}
      {byModel.map((m) => {
        const rows = sampled.filter((c) => c.model_id === m).sort((a, b) => a.factor_level.localeCompare(b.factor_level))
        const accs = rows.map((r) => r.accuracy as number)
        const mean = accs.reduce((a, b) => a + b, 0) / accs.length
        const spread = Math.max(...accs) - Math.min(...accs)
        const lo = Math.min(...accs), hi = Math.max(...accs)
        return (
          <section key={m} aria-label={`${shortLabel(m)} sampling spread`}>
            <h3>{shortLabel(m)} <span className="note">mean {fmtPct(mean)} · spread {(spread * 100).toFixed(2)} pp</span></h3>
            <div className="table-wrap"><table className="data">
              <thead><tr><th>Seed</th><th>Score</th><th>Δ vs mean</th><th>n</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.run_id}>
                    <td><code>{r.factor_level}</code></td>
                    <td className="num">{fmtPct(r.accuracy)}</td>
                    <td className="num">{r.accuracy !== null ? `${((r.accuracy - mean) * 100 >= 0 ? "+" : "")}${((r.accuracy - mean) * 100).toFixed(2)} pp` : "—"}</td>
                    <td className="num">{r.n ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
            <p className="note">Range {fmtPct(lo)} – {fmtPct(hi)}. A spread wider than the model gaps on the Rankings page would make conclusions seed-sensitive.</p>
          </section>
        )
      })}
    </div>
  )
}
