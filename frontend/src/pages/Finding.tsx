import * as React from "react"
import { Delta, MethodNote } from "../components"
import { fmtPct, shortLabel } from "../data"
import type { SiteData } from "../data"

/** Centerpiece: score deltas + rank movement for control vs each variant. */
export function Finding({ site }: { site: SiteData }) {
  const [key, setKey] = React.useState(
    () => site.ranking_comparisons.find((c) => c.variant_key === "prompt_id=5shot")?.variant_key
      ?? site.ranking_comparisons[0]?.variant_key ?? "")
  const comp = site.ranking_comparisons.find((c) => c.variant_key === key)
  if (!comp) return <p className="note">No ranking comparisons in the current export.</p>
  return (
    <div>
      <section aria-label="Configuration effect on rankings">
        <h2>Configuration-induced ranking changes</h2>
        <p className="note">
          Each comparison below is <strong>control vs one variant configuration</strong> over
          the models measured in both. Score deltas are variant − control.
        </p>
        <div className="filters">
          <label>Variant configuration
            <select value={key} onChange={(e) => setKey(e.target.value)} aria-label="Variant configuration">
              {site.ranking_comparisons.map((c) => (
                <option key={c.variant_key} value={c.variant_key}>
                  {c.variant_key} {c.reordered ? "· ranking changed" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="finding" role="figure" aria-label={`${comp.base_key} versus ${comp.variant_key}`}>
          <p className="rankline">CONTROL&nbsp;&nbsp;{comp.base_order.join("  ›  ")}</p>
          <p className="rankline">VARIANT&nbsp;&nbsp;{comp.variant_order.join("  ›  ")}</p>
          <p className="note" style={{ marginBottom: 0 }}>
            {comp.reordered
              ? <strong>Ranking changed under {comp.variant_key}.</strong>
              : <>Ranking preserved under {comp.variant_key}.</>}{" "}
            Kendall τ = {comp.tau !== null ? comp.tau.toFixed(2) : "n/a"} ·{" "}
            {comp.n_reversals} pairwise reversal{comp.n_reversals === 1 ? "" : "s"} ·{" "}
            {comp.n_shared_models} shared models
            {comp.excluded_from_base.length > 0 && (
              <> · excluded (not measured in variant): {comp.excluded_from_base.map(shortLabel).join(", ")}</>
            )}.
          </p>
        </div>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Model</th><th>Control</th><th>Variant</th><th>Δ</th><th>Rank</th><th>Move</th></tr></thead>
            <tbody>
              {comp.members.map((m) => (
                <tr key={m.model_id}>
                  <td>{shortLabel(m.model_id)}</td>
                  <td className="num">{fmtPct(m.base_score)}</td>
                  <td className="num">{fmtPct(m.variant_score)}</td>
                  <td><Delta x={m.delta} /></td>
                  <td className="num">{m.base_rank} → {m.variant_rank}</td>
                  <td className="num">{m.rank_move === 0 ? "—" : `${m.rank_move > 0 ? "↓" : "↑"} ${Math.abs(m.rank_move)}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <MethodNote site={site} />
      </section>

      <section aria-label="All variant effects">
        <h2>All measured configuration effects</h2>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Variant</th><th>Ranking</th><th>τ vs control</th><th>Reversals</th></tr></thead>
            <tbody>
              {site.ranking_comparisons.map((c) => (
                <tr key={c.variant_key}>
                  <td><code>{c.variant_key}</code></td>
                  <td>{c.reordered ? <strong>changed</strong> : "preserved"}</td>
                  <td className="num">{c.tau !== null ? c.tau.toFixed(2) : "n/a"}</td>
                  <td className="num">{c.n_reversals}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
