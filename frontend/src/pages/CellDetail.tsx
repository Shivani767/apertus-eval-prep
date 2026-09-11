import type * as React from "react"
import { CopyButton } from "../components"
import type { SiteCell, SiteData } from "../data"
import { fmtPct } from "../data"
import { shortLabel } from "../data"

function kv(label: string, value: React.ReactNode) {
  return <tr><td>{label}</td><td>{value}</td></tr>
}

/** Full detail for one cell: config, result, runtime, evidence, provenance. */
export function CellDetail({ site, runId, back }: { site: SiteData; runId: string; back: () => void }) {
  const cell: SiteCell | undefined = site.cells.find((c) => c.run_id === runId)
  if (!cell) return <div><p className="note">Unknown run id <code>{runId}</code>.</p><button className="copybtn" type="button" onClick={back}>Back</button></div>
  const fail = site.failures.find((f) => f.run_id === runId)
  const stat = site.statistics.comparisons.find((s) => cell.factor !== "control" && s.variant_key === cell.config_key && s.model_id === cell.model_id)
  const cmds = site.reproducibility.commands[runId]
  const lat = cell.latency
  return (
    <div>
      <p><button className="copybtn" type="button" onClick={back}>← All experiments</button></p>
      <h2>{shortLabel(cell.model_id)} · <code>{cell.config_key}</code></h2>
      <p><span className={`badge ${cell.status === "MEASURED" ? "measured" : cell.status === "SAMPLED" ? "sampled" : "pending"}`}>{cell.status}</span> <span className="note">{cell.provenance}</span></p>

      <h3>Configuration</h3>
      <div className="table-wrap"><table className="data"><tbody>
        {kv("model", <code>{cell.model_id}</code>)}
        {kv("factor", <code>{cell.factor} = {cell.factor_level}</code>)}
        {Object.entries(cell.axes).map(([k, v]) => kv(k, v === null || v === undefined || v === "" ? "Not measured" : <code>{String(v)}</code>))}
        {kv("tasks", Object.keys(cell.tasks).join(", ") || "Not measured")}
        {kv("config hash", <code>{cell.config_hash ?? "Not measured"}</code>)}
      </tbody></table></div>

      <h3>Result</h3>
      <div className="table-wrap"><table className="data"><tbody>
        {kv("score", <strong className="num">{fmtPct(cell.accuracy)}</strong>)}
        {kv("correct / n", cell.correct !== null && cell.n !== null ? <span className="num">{cell.correct} / {cell.n}</span> : "Not measured")}
        {kv("95% CI", cell.accuracy_ci95 ? <span className="num">{fmtPct(cell.accuracy_ci95[0])} – {fmtPct(cell.accuracy_ci95[1])}</span> : "Not measured")}
        {fail && kv("failures", <span className="num">{Object.entries(fail.counts).map(([k, v]) => `${k}: ${v}`).join(" · ")}</span>)}
      </tbody></table></div>

      <h3>Runtime</h3>
      <div className="table-wrap"><table className="data"><tbody>
        {kv("mean latency", lat?.e2e_ms_mean ? <span className="num">{lat.e2e_ms_mean.toFixed(0)} ms</span> : "Unavailable")}
        {kv("throughput", lat?.tokens_per_sec_mean ? <span className="num">{lat.tokens_per_sec_mean.toFixed(1)} tok/s</span> : "Unavailable")}
        {kv("mean TTFT", lat?.ttft_ms_mean ? <span className="num">{lat.ttft_ms_mean.toFixed(0)} ms</span> : "Unavailable")}
      </tbody></table></div>

      <h3>Evidence</h3>
      {stat ? (
        <div className="table-wrap"><table className="data"><tbody>
          {kv("Δ vs control", <span className="num">{fmtPct(stat.delta)} [{stat.delta_ci95[0] !== null ? fmtPct(stat.delta_ci95[0]) : "?"} – {stat.delta_ci95[1] !== null ? fmtPct(stat.delta_ci95[1]) : "?"}]</span>)}
          {kv("permutation p (BH)", stat.perm_p_bh !== null ? <span className="num">{stat.perm_p_bh < 0.001 ? "< 0.001" : stat.perm_p_bh.toFixed(4)}</span> : "Not applicable")}
          {kv("McNemar p", <span className="num">{stat.mcnemar.p_value}</span>)}
          {kv("Cohen's h", stat.cohens_h !== null ? <span className="num">{stat.cohens_h.toFixed(3)}</span> : "Not applicable")}
          {kv("paired items", <span className="num">{stat.n_paired} (dropped {stat.n_dropped})</span>)}
        </tbody></table></div>
      ) : <p className="note">No paired statistical comparison for this cell (control cells and cells without a measured control are descriptive only).</p>}

      <h3>Provenance</h3>
      <div className="table-wrap"><table className="data"><tbody>
        {kv("artifact", <code>{cell.path ?? "none"}</code>)}
        {kv("git commit", <code>{(cell.git_commit ?? "unknown").slice(0, 12)}</code>)}
        {kv("recorded", cell.utc ?? "unknown")}
      </tbody></table></div>
      {cmds && (
        <>
          <h3>Reproduce</h3>
          <pre>{cmds.sweep_command}</pre>
          <p><CopyButton text={cmds.sweep_command} label="Copy sweep command" /></p>
        </>
      )}
    </div>
  )
}
