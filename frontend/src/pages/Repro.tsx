import * as React from "react"
import { CopyButton } from "../components"
import { shortLabel } from "../data"
import type { SiteData } from "../data"

/** Reproducibility: question → config → result → artifact → command. */
export function Repro({ site }: { site: SiteData }) {
  const r = site.reproducibility
  const [onlyFail, setOnlyFail] = React.useState(false)
  const [open, setOpen] = React.useState<string | null>(null)
  const rows = r.rows.filter((x) => !onlyFail || !x.all_match)
  return (
    <div>
      <h2>Reproducibility</h2>
      <p className="note">
        Research question → experiment → configuration → result → statistical analysis →
        artifact → reproduction command. Every cell below carries its exact replay command
        (read from the CLI implementation, not invented).
      </p>
      <p className="note">
        Commit <code>{r.git_commit?.slice(0, 12) ?? "unknown"}</code> · verification{" "}
        <strong>{r.n_pass}/{r.n_verified} pass</strong>
        {r.n_fail > 0 && <> · <strong>{r.n_fail} with deviations</strong> (shown, investigated — see below)</>}.
      </p>
      <div className="filters">
        <label style={{ flexDirection: "row", alignItems: "center", gap: "0.4rem" }}>
          <input type="checkbox" checked={onlyFail} onChange={(e) => setOnlyFail(e.target.checked)} />
          Only rows with deviations
        </label>
      </div>
      <div className="table-wrap"><table className="data">
        <thead><tr><th>Run</th><th>Config hash</th><th>Verification</th><th>Detail</th></tr></thead>
        <tbody>
          {rows.map((x) => (
            <React.Fragment key={x.run_id}>
              <tr>
                <td><code>{shortLabel(x.run_id.split("_")[0])}…</code><br /><span className="note">{x.run_id}</span></td>
                <td><code>{x.config_hash?.slice(0, 12) ?? "—"}</code></td>
                <td>{x.all_match ? "pass" : <strong>deviations: {x.failed.join(", ")}</strong>}</td>
                <td><button className="copybtn" type="button" onClick={() => setOpen(open === x.run_id ? null : x.run_id)} aria-expanded={open === x.run_id}>{open === x.run_id ? "Hide" : "Show"}</button></td>
              </tr>
              {open === x.run_id && (
                <tr><td colSpan={4}>
                  <table className="data"><thead><tr><th>Check</th><th>Expected</th><th>Observed</th><th>Match</th></tr></thead>
                    <tbody>
                      {(r.detail[x.run_id]?.checks ?? []).map((c) => (
                        <tr key={c.name}><td><code>{c.name}</code></td><td className="num">{String(c.expected)}</td><td className="num">{String(c.observed)}</td>
                          <td>{c.match === true ? "yes" : c.match === false ? <strong>NO</strong> : "n/a"}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  {r.commands[x.run_id] && (
                    <>
                      <pre>{r.commands[x.run_id].sweep_command}</pre>
                      <p><CopyButton text={r.commands[x.run_id].sweep_command} label="Copy command" /></p>
                    </>
                  )}
                </td></tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table></div>
      {r.n_fail > 0 && (
        <div className="warnbox">
          Deviations are reported, not hidden: {r.n_fail} sampled cell(s) differ between
          registry metadata and artifact (git commit / rounding), and are flagged for
          re-verification before any paper claim uses them.
        </div>
      )}
      <h3>Reproduce locally</h3>
      <pre>pip install -e .{"\n"}python -m apertus_eval_prep reproduce --run-id &lt;RUN_ID&gt; --registry results/registry_paper.jsonl</pre>
    </div>
  )
}
