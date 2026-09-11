import { Stat } from "../components"
import { shortLabel } from "../data"
import type { SiteData } from "../data"

/** ERS section: provisional score with components, ablation, disclaimer. */
export function Reliability({ site }: { site: SiteData }) {
  const r = site.reliability
  return (
    <div>
      <h2>Evaluation Reliability Score</h2>
      <div className="warnbox">
        <strong>Provisional research diagnostic, not a validated universal metric.</strong>{" "}
        {r.disclaimer}
      </div>
      <div className="grid cols-4" role="list">
        <Stat value={r.ers !== null ? r.ers.toFixed(3) : "n/a"} label="ERS" sub={`${r.n_components} components`} />
        {Object.entries(r.components).map(([k, v]) => (
          <Stat key={k} value={v !== null ? v.toFixed(3) : "n/a"} label={k} sub={v === null ? "unavailable — excluded" : `weight ${r.weights_used[k] ?? "?"}`} />
        ))}
      </div>
      <h3>What enters the score</h3>
      <div className="table-wrap"><table className="data"><tbody>
        <tr><td><strong>CI separation</strong></td><td className="note">Fraction of model pairs with non-overlapping 95% Wilson CIs over {r.n_configs_in_matrix} shared configs.</td></tr>
        <tr><td><strong>Bootstrap τ</strong></td><td className="note">Mean Kendall τ vs resampled-config rankings (τ={r.bootstrap.mean_tau !== null ? r.bootstrap.mean_tau.toFixed(3) : "n/a"}, P(reversal)={r.bootstrap.p_any_reversal !== null ? r.bootstrap.p_any_reversal.toFixed(3) : "n/a"}).</td></tr>
        <tr><td><strong>Config stability</strong></td><td className="note">1 − within-model / between-model spread ratio across configs.</td></tr>
        <tr><td><strong>Seed stability</strong></td><td className="note">{r.components.seed_stability === null ? "Unavailable in current data — excluded, not imputed." : "From the sampled arm."}</td></tr>
      </tbody></table></div>
      <p className="note">
        Models in score: {r.models.map(shortLabel).join(", ")}.
        {r.excluded_models.length > 0 && <> Excluded (&lt; 2 configs): {r.excluded_models.map(shortLabel).join(", ")}.</>}
        {" "}Sampled configs are not ranking configs: {r.skipped_configs.join(", ") || "none"}.
      </p>
      <h3>Ablation (drop one component)</h3>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Dropped</th><th>ERS without</th><th>Δ</th></tr></thead>
        <tbody>
          {Object.entries(r.ablation).map(([k, v]) => (
            <tr key={k}><td>{k}</td>
              <td className="num">{v.ers_without !== null ? v.ers_without.toFixed(3) : "n/a"}</td>
              <td className="num">{v.delta !== null ? v.delta.toFixed(3) : "n/a"}</td></tr>
          ))}
        </tbody>
      </table></div>
    </div>
  )
}
