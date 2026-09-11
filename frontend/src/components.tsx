import * as React from "react"
import { fmtDelta, fmtP, fmtPct, shortLabel } from "./data"
import type { SiteData } from "./data"

/** One statistic box. Value is a pre-rendered string — never null-coerced here. */
export function Stat({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="v">{value}</div>
      <div className="l">{label}</div>
      {sub && <div className="s">{sub}</div>}
    </div>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const cls = status === "MEASURED" ? "measured" : status === "SAMPLED" ? "sampled" : status === "PENDING" ? "pending" : "derived"
  return <span className={`badge ${cls}`}>{status}</span>
}

export function Delta({ x, digits = 2 }: { x: number | null | undefined; digits?: number }) {
  if (x === null || x === undefined || Number.isNaN(x)) return <span className="num">Not measured</span>
  const cls = x > 0 ? "delta-up" : x < 0 ? "delta-down" : ""
  return <span className={`num ${cls}`}>{fmtDelta(x, digits)}</span>
}

export function PValue({ x }: { x: number | null | undefined }) {
  return <span className="num">{fmtP(x)}</span>
}

/** Copy-to-clipboard button for reproduction commands. */
export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = React.useState(false)
  return (
    <button
      className="copybtn"
      type="button"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setDone(true)
          window.setTimeout(() => setDone(false), 1500)
        })
      }}
    >
      {done ? "Copied" : label}
    </button>
  )
}

export function MethodNote({ site }: { site: SiteData }) {
  return (
    <p className="note">
      Source: <code>{site.registry}</code>, export <code>{site.generated_utc}</code>.{" "}
      <a href="https://github.com/Shivani767/apertus-eval-prep">Repository</a> — every
      figure below is recomputed from committed run artifacts; no number is hand-entered.
    </p>
  )
}

export { fmtPct, fmtP, shortLabel }
export type { SiteData }
