import * as React from "react"
import { Delta, PValue } from "../components"
import { fmtPct, shortLabel } from "../data"
import type { SiteData } from "../data"

const METHOD_DOCS: [string, string][] = [
  ["Effect size (Cohen's h)", "Standardized difference between two proportions. |h| ≈ 0.2 is small, ≈ 0.5 medium, ≈ 0.8 large — a descriptive scale, not a significance claim."],
  ["Confidence intervals (paired bootstrap)", "Items are resampled jointly (same ids into both arms) so per-item pairing is preserved. A CI excluding zero is descriptive evidence of a systematic difference."],
  ["Sign-flip permutation test", "Under H0 each paired difference is equally likely +d or −d; signs are flipped at random (seeded Monte-Carlo, not exact enumeration)."],
  ["McNemar's test", "Continuity-corrected χ² on the discordant items (one right / other wrong). Appropriate for paired binary outcomes."],
  ["Holm–Bonferroni (FWER)", "Step-down adjusted p-values controlling the family-wise error rate across all comparisons on this page."],
  ["Benjamini–Hochberg (FDR)", "Step-up adjusted p-values controlling the false discovery rate — less conservative than Holm."],
]

/** Statistical evidence: every comparison with CI, p, adjusted p, effect. */
export function Stats({ site }: { site: SiteData }) {
  const s = site.statistics
  const [model, setModel] = React.useState("")
  const [showMethods, setShowMethods] = React.useState(false)
  const rows = s.comparisons.filter((c) => !model || c.model_id === model)
  const sig = rows.filter((c) => c.ci_excludes_zero).length
  return (
    <div>
      <h2>Statistical evidence</h2>
      <p className="note">
        {s.n_comparisons} control-vs-variant comparisons on paired items (n_boot={s.n_boot},
        n_perm={s.n_perm}, seed={s.seed}). {sig} have a bootstrap CI excluding zero.{" "}
        Adjusted p-values correct across all {s.n_tests_corrected} tests.{" "}
        <strong>Descriptive</strong> summaries (rankings, deltas) are distinct from{" "}
        <strong>statistical evidence</strong> (CIs, p-values) below — do not overinterpret p-values.
      </p>
      <p><button className="copybtn" type="button" onClick={() => setShowMethods(!showMethods)} aria-expanded={showMethods}>
        {showMethods ? "Hide" : "Show"} method glossary
      </button></p>
      {showMethods && (
        <div className="table-wrap"><table className="data"><tbody>
          {METHOD_DOCS.map(([t, d]) => <tr key={t}><td><strong>{t}</strong></td><td className="note">{d}</td></tr>)}
          <tr><td><strong>Engine</strong></td><td className="note">Same functions the paper pipeline uses (<code>stats.py</code>); numbers here equal the paper numbers. See <code>docs/STATISTICAL_METHODOLOGY*.md</code> in the repo.</td></tr>
        </tbody></table></div>
      )}
      <div className="filters">
        <label>Model
          <select value={model} onChange={(e) => setModel(e.target.value)} aria-label="Filter by model">
            <option value="">All models</option>
            {site.models.map((m) => <option key={m.model_id} value={m.model_id}>{m.label}</option>)}
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>Model</th><th>Variant</th><th>Δ vs control [95% CI]</th><th>p (perm)</th><th>p (Holm)</th><th>p (BH)</th><th>McNemar p</th><th>h</th><th>n</th></tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={`${c.model_id} ${c.variant_key}`}>
                <td>{shortLabel(c.model_id)}</td>
                <td><code>{c.variant_key}</code></td>
                <td className="num"><Delta x={c.delta} /> [{c.delta_ci95[0] !== null ? fmtPct(c.delta_ci95[0]) : "?"} – {c.delta_ci95[1] !== null ? fmtPct(c.delta_ci95[1]) : "?"}]</td>
                <td><PValue x={c.perm_p} /></td>
                <td><PValue x={c.perm_p_holm} /></td>
                <td><PValue x={c.perm_p_bh} /></td>
                <td><PValue x={c.mcnemar.p_value} /></td>
                <td className="num">{c.cohens_h !== null ? c.cohens_h.toFixed(2) : "n/a"}</td>
                <td className="num">{c.n_paired}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
