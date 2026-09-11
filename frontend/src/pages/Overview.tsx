import { Delta, MethodNote, Stat, StatusBadge } from "../components"
import { fmtPct, shortLabel } from "../data"
import type { SiteData } from "../data"

/** Landing / overview: research question, live coverage, the finding. */
export function Overview({ site }: { site: SiteData }) {
  const c = site.coverage
  const done = c.planned_cells ? `${c.measured}/${c.planned_cells}` : `${c.measured}`
  const five = site.ranking_comparisons.find((x) => x.variant_key === "prompt_id=5shot")
  return (
    <div>
      <section aria-label="Research question">
        <h2>Research question</h2>
        <p>
          <strong>How robust are conclusions about relative LLM capability to reasonable
          changes in evaluation configuration?</strong>
        </p>
        <p className="note">
          Model × task × evaluation configuration → measurement → research conclusion.
          LLM benchmark scores are measurements produced by an evaluation configuration,
          not immutable intrinsic properties of a model.
        </p>
        <div className="grid cols-4" role="list" aria-label="Experiment coverage">
          <Stat value={done} label="experiment cells" sub={c.planned_cells ? `${Math.round((c.completion ?? 0) * 100)}% of planned matrix` : undefined} />
          <Stat value={`${c.n_models}`} label="models" sub={site.models.map((m) => m.label).join(", ")} />
          <Stat value={`${c.n_configs}`} label="configurations" sub={`${c.n_factors} factors`} />
          <Stat value={`${site.statistics.n_comparisons}`} label="paired comparisons" sub="bootstrap + permutation + McNemar" />
        </div>
        <div className="grid cols-4" style={{ marginTop: "1rem" }} role="list" aria-label="Analysis status">
          <Stat value={`${Object.keys(site.reproducibility.commands).length}`} label="reproducible cells" sub={`${site.reproducibility.n_pass}/${site.reproducibility.n_verified} deviation checks pass`} />
          <Stat value={site.reliability.ers !== null ? site.reliability.ers.toFixed(3) : "n/a"} label="ERS (provisional)" sub={`${site.reliability.n_components} components`} />
          <Stat value={`${site.failures.reduce((a, f) => a + f.total, 0).toLocaleString()}`} label="scored items" sub="per-item failure taxonomy" />
          <Stat value={`${site.coverage.pending}`} label="pending cells" sub="shown, never zero-filled" />
        </div>
        <MethodNote site={site} />
      </section>

      <section aria-label="The finding">
        <h2>The finding</h2>
        {five && five.reordered ? (
          <div className="finding" role="figure" aria-label="Control versus 5-shot ranking reversal">
            <p style={{ marginTop: 0 }}>
              <strong>Configuration changes can alter measured performance and model rankings.</strong>{" "}
              Under the default prompt the order is{" "}
              <strong>{five.base_order.join(" › ")}</strong>; with 5-shot examples it becomes{" "}
              <strong>{five.variant_order.join(" › ")}</strong>.
            </p>
            {five.members.map((m) => (
              <p className="rankline" key={m.model_id}>
                {shortLabel(m.model_id)}: {fmtPct(m.base_score)} → {fmtPct(m.variant_score)} (
                <Delta x={m.delta} />; rank {m.base_rank} → {m.variant_rank})
              </p>
            ))}
            <p className="note">
              Kendall τ = {five.tau !== null ? five.tau.toFixed(2) : "n/a"} between the two
              orderings over {five.n_shared_models} shared models; {five.n_reversals} pairwise
              reversal{five.n_reversals === 1 ? "" : "s"}. Derived from measured cell accuracies —
              see Rankings and Statistics for the full evidence.
            </p>
          </div>
        ) : (
          <p className="note">No control-vs-5-shot reordering is supported by the current data.</p>
        )}
      </section>

      <section aria-label="Coverage">
        <h2>Experiment coverage</h2>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Model</th><th>Cells</th><th>Mean</th><th>Min</th><th>Max</th><th>Spread</th></tr></thead>
            <tbody>
              {site.models.map((m) => (
                <tr key={m.model_id}>
                  <td>{m.label}</td>
                  <td className="num">{m.n_cells}</td>
                  <td className="num">{fmtPct(m.mean_accuracy)}</td>
                  <td className="num">{fmtPct(m.min_accuracy)}</td>
                  <td className="num">{fmtPct(m.max_accuracy)}</td>
                  <td className="num">{m.spread !== null ? `${(m.spread * 100).toFixed(2)} pp` : "Not measured"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h3>Configurations</h3>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Configuration</th><th>Factor</th><th>Models measured</th><th>Pending</th></tr></thead>
            <tbody>
              {site.configs.map((g) => (
                <tr key={g.config_key}>
                  <td><code>{g.config_key}</code></td>
                  <td><code>{g.factor}={g.factor_level}</code></td>
                  <td className="num">{g.n_models}</td>
                  <td className="num">{g.n_pending > 0 ? g.n_pending : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
