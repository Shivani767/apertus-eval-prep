import * as React from "react"
import { Delta, PValue, Stat, StatusBadge } from "../components"
import type { SiteData } from "../data"

const ROUTES = [
  ["overview", "Overview"],
  ["finding", "The Finding"],
  ["explorer", "Experiments"],
  ["rankings", "Rankings"],
  ["matrix", "Matrix"],
  ["stats", "Statistics"],
  ["reliability", "Reliability"],
  ["failures", "Failures"],
  ["cost", "Cost"],
  ["sampling", "Sampling"],
  ["repro", "Reproducibility"],
  ["method", "Methodology"],
] as const

export type Route = (typeof ROUTES)[number][0]

const TITLES: Record<Route, string> = {
  overview: "Overview",
  finding: "The Finding",
  explorer: "Experiment Explorer",
  rankings: "Ranking Stability",
  matrix: "Results Matrix",
  stats: "Statistical Evidence",
  reliability: "Evaluation Reliability Score",
  failures: "Failure Analysis",
  cost: "Backend, Quantization & Cost",
  sampling: "Sampling Stability",
  repro: "Reproducibility",
  method: "Methodology & Limitations",
}

export function routeFromHash(): Route {
  const h = window.location.hash.replace(/^#\/?/, "").split("?")[0]
  return (ROUTES.some(([r]) => r === h) ? h : "overview") as Route
}

export function filtersFromHash(): Record<string, string> {
  const q = window.location.hash.split("?")[1] ?? ""
  const out: Record<string, string> = {}
  for (const [k, v] of new URLSearchParams(q)) out[k] = v
  return out
}

export function Header({ site }: { site: SiteData }) {
  const c = site.coverage
  return (
    <header className="site-header">
      <a className="skip-link" href="#main">Skip to content</a>
      <p className="kicker">Apertus Eval Prep · controlled LLM evaluation study</p>
      <h1>LLM benchmarks are measurements, not intrinsic properties.</h1>
      <p className="hero-sub">
        A controlled study of how prompts, backends, quantization, sampling, and other
        evaluation choices affect measured capability and model rankings.
      </p>
      <p className="meta-row">
        Registry <code>{site.registry}</code> · {c.measured}/{c.planned_cells ?? "?"} cells ·{" "}
        {site.models.length} models · export <code>{site.generated_utc}</code>
      </p>
    </header>
  )
}

export function Nav({ route, go }: { route: Route; go: (r: Route) => void }) {
  return (
    <nav className="main-nav" aria-label="Sections">
      {ROUTES.map(([r, label]) => (
        <button key={r} type="button" onClick={() => go(r)} aria-current={route === r ? "page" : undefined}>
          {label}
        </button>
      ))}
    </nav>
  )
}

export function Footer({ site }: { site: SiteData }) {
  return (
    <footer className="site-foot">
      Apertus Eval Prep ·{" "}
      <a href="https://github.com/Shivani767/apertus-eval-prep">github.com/Shivani767/apertus-eval-prep</a>{" "}
      · data export <code>{site.generated_utc}</code> from <code>{site.registry}</code> · commit{" "}
      <code>{site.reproducibility.git_commit?.slice(0, 8) ?? "unknown"}</code>
    </footer>
  )
}

export { TITLES, Delta, PValue, Stat, StatusBadge }
