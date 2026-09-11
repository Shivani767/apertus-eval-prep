import { useCallback, useEffect, useState } from "react"
import { loadSite } from "./data"
import type { SiteData } from "./data"
import { Footer, Header, Nav, TITLES, routeFromHash } from "./pages/chrome"
import type { Route } from "./pages/chrome"
import { Overview } from "./pages/Overview"
import { Finding } from "./pages/Finding"
import { Explorer } from "./pages/Explorer"
import { CellDetail } from "./pages/CellDetail"
import { Rankings } from "./pages/Rankings"
import { Matrix } from "./pages/Matrix"
import { Stats } from "./pages/Stats"
import { Reliability } from "./pages/Reliability"
import { Failures } from "./pages/Failures"
import { Cost } from "./pages/Cost"
import { Sampling } from "./pages/Sampling"
import { Repro } from "./pages/Repro"
import { Method } from "./pages/Method"

export default function App() {
  const [site, setSite] = useState<SiteData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [route, setRoute] = useState<Route>(() => routeFromHash())
  const [cellRun, setCellRun] = useState<string | null>(null)
  const [compareKey, setCompareKey] = useState<string | null>(null)

  useEffect(() => {
    loadSite().then(setSite).catch((e: unknown) => setErr(String(e)))
    const onHash = () => {
      if (!window.location.hash.startsWith("#/cell/")) setCellRun(null)
      setRoute(routeFromHash())
    }
    window.addEventListener("hashchange", onHash)
    return () => window.removeEventListener("hashchange", onHash)
  }, [])

  const go = useCallback((r: Route) => {
    setCellRun(null)
    setCompareKey(null)
    window.location.hash = `#/${r}`
    setRoute(r)
    document.title = `Apertus Eval Prep — ${TITLES[r]}`
  }, [])

  const goCell = useCallback((runId: string) => {
    setCellRun(runId)
    window.location.hash = `#/cell/${encodeURIComponent(runId)}`
    document.title = `Apertus Eval Prep — Experiment ${runId}`
  }, [])

  const goCompare = useCallback((variantKey: string) => {
    setCompareKey(variantKey)
    window.location.hash = `#/finding?variant=${encodeURIComponent(variantKey)}`
    setRoute("finding")
  }, [])

  useEffect(() => {
    const m = window.location.hash.match(/^#\/cell\/(.+)$/)
    if (m) setCellRun(decodeURIComponent(m[1]))
  }, [])

  if (err) return <div className="app"><p className="errbox">Failed to load data: {err}</p></div>
  if (!site) return <div className="app"><p>Loading research data…</p></div>

  return (
    <div className="app">
      <Header site={site} />
      <Nav route={cellRun ? "explorer" : route} go={go} />
      <main id="main">
        {cellRun ? (
          <CellDetail site={site} runId={cellRun} back={() => go("explorer")} />
        ) : (
          <>
            {route === "overview" && <Overview site={site} />}
            {route === "finding" && <Finding site={site} />}
            {route === "explorer" && <Explorer site={site} goCell={goCell} />}
            {route === "rankings" && <Rankings site={site} goCompare={goCompare} />}
            {route === "matrix" && <Matrix site={site} goCell={goCell} />}
            {route === "stats" && <Stats site={site} />}
            {route === "reliability" && <Reliability site={site} />}
            {route === "failures" && <Failures site={site} />}
            {route === "cost" && <Cost site={site} />}
            {route === "sampling" && <Sampling site={site} />}
            {route === "repro" && <Repro site={site} />}
            {route === "method" && <Method site={site} />}
          </>
        )}
      </main>
      <Footer site={site} />
    </div>
  )
}

