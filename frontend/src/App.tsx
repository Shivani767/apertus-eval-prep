import { useEffect, useState } from 'react'
import { DashboardData, loadDashboard, loadERS, loadFailures } from './data'

type Tab = 'overview' | 'rankings' | 'reliability' | 'failures'

export default function App() {
  const [tab, setTab] = useState<Tab>('overview')
  const [d, setD] = useState<DashboardData | null>(null)
  const [ers, setErs] = useState<DashboardData['ers'] | null>(null)
    const [failures, setFailures] = useState<Record<string, any> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([loadDashboard(), loadERS(), loadFailures()])
      .then(([dash, e, f]) => { setD(dash); setErs(e); setFailures(f) })
      .catch((e: unknown) => setErr(String(e)))
  }, [])

  if (err) return <p style={{ color: 'red' }}>Failed to load data: {err}</p>
  if (!d) return <p>Loading dashboard data from /data/ …</p>

  const models = Object.entries(d.models as Record<string, { n_cells: number; mean_accuracy: number; min_accuracy: number; max_accuracy: number }>)

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <h1>Apertus Eval Prep — Research Dashboard</h1>
      <p style={{ color: '#666' }}>Registry: {d.registry} — {d.n_rows} rows</p>

      <nav style={{ display: 'flex', gap: 8, margin: '16px 0', borderBottom: '1px solid #ddd' }}>
        {(['overview', 'rankings', 'reliability', 'failures'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 16px', border: 'none', cursor: 'pointer', background: 'none',
            borderBottom: tab === t ? '2px solid #0066cc' : '2px solid transparent',
            fontWeight: tab === t ? 600 : 400,
          }}>{t[0].toUpperCase() + t.slice(1)}</button>
        ))}
      </nav>

      {tab === 'overview' && <Overview models={models} />}
      {tab === 'rankings' && <Rankings models={models} />}
      {tab === 'reliability' && <Reliability ers={ers} deviations={d.deviations} />}
      {tab === 'failures' && <Failures failures={failures} />}
    </div>
  )
}

function Overview({ models }: { models: [string, { n_cells: number; mean_accuracy: number; min_accuracy: number; max_accuracy: number }][] }) {
  return (
    <section>
      <h2>Models (measured cells only)</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr style={{ textAlign: 'left', borderBottom: '1px solid #ddd' }}>
          <th>model</th><th>cells</th><th>mean acc</th><th>min</th><th>max</th>
        </tr></thead>
        <tbody>{models.map(([model, m]) => (
          <tr key={model} style={{ borderBottom: '1px solid #eee' }}>
            <td>{model}</td><td>{m.n_cells}</td><td>{(m.mean_accuracy * 100).toFixed(1)}%</td>
            <td>{(m.min_accuracy * 100).toFixed(1)}%</td><td>{(m.max_accuracy * 100).toFixed(1)}%</td>
          </tr>
        ))}</tbody>
      </table>
    </section>
  )
}

function Rankings({ models }: { models: [string, { n_cells: number; mean_accuracy: number; min_accuracy: number; max_accuracy: number }][] }) {
  const sorted = [...models].sort((a, b) => b[1].mean_accuracy - a[1].mean_accuracy)
  return (
    <section>
      <h2>Model Rankings</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr style={{ textAlign: 'left', borderBottom: '1px solid #ddd' }}>
          <th>rank</th><th>model</th><th>mean accuracy</th>
        </tr></thead>
        <tbody>{sorted.map(([model, m], i) => (
          <tr key={model} style={{ borderBottom: '1px solid #eee' }}>
            <td>{i + 1}</td><td>{model}</td><td>{(m.mean_accuracy * 100).toFixed(1)}%</td>
          </tr>
        ))}</tbody>
      </table>
    </section>
  )
}

function Reliability({ ers, deviations }: { ers: any; deviations: any }) {
  if (!ers) return <p>No ERS data.</p>
  return (
    <section>
      <h2>Evaluation Reliability Score (DERIVED, provisional)</h2>
      <p style={{ fontSize: 24, fontWeight: 600 }}>ERS: {ers.ers ?? 'n/a'} ({ers.n_components} components)</p>
      <ul>
        {Object.entries(ers.components || {}).map(([k, v]) => (
          <li key={k}>{k}: {v === null ? 'n/a' : typeof v === 'number' ? v.toFixed(3) : String(v)}</li>
        ))}
      </ul>
      {ers.bootstrap && <p style={{ color: '#666' }}>bootstrap tau={ers.bootstrap.mean_tau?.toFixed(3)}, p(reversal)={ers.bootstrap.p_any_reversal?.toFixed(3)}</p>}
      {deviations && (
        <p style={{ color: '#666' }}>Artifacts verified: {deviations.n_verified} total,
           {deviations.n_pass} pass / {deviations.n_fail} fail
           {deviations.details_fail.length > 0 && `, ${deviations.details_fail.length} with deviations`}.</p>
      )}
    </section>
  )
}

function Failures({ failures }: { failures: Record<string, any> | null }) {
  if (!failures) return <p>No failure data.</p>
  return (
    <section>
      <h2>Failure taxonomy (measured per-item counts)</h2>
      {Object.entries(failures).map(([label, rep]: [string, any]) => (
        <div key={label} style={{ marginBottom: 24 }}>
          <h3>{label}</h3>
          <p>{rep.items} items, overall failure rate: {Math.round(rep.overall_failure_rate * 10000) / 100}%</p>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr style={{ textAlign: 'left', borderBottom: '1px solid #ddd' }}>
              <th>category</th><th>count</th><th>rate</th>
            </tr></thead>
            <tbody>{Object.entries(rep.categories).map(([cat, v]: [string, any]) => (
              <tr key={cat} style={{ borderBottom: '1px solid #eee' }}>
                <td>{cat}</td><td>{v.count}</td><td>{Math.round(v.rate * 10000) / 100}%</td>
              </tr>
            ))}</tbody>
                    </table>
        </div>
      ))}
    </section>
  )
}