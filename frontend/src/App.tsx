import { useState } from 'react'
import dashboardData from './data/dashboard/dashboard.json'

type Tab = 'overview' | 'rankings' | 'reliability' | 'failures'

export default function App() {
  const [tab, setTab] = useState<Tab>('overview')
  const d = dashboardData
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
      {tab === 'reliability' && <Reliability ers={d.ers} />}
      {tab === 'failures' && <Failures deviations={d.deviations} failures={d.failures} />}
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

function Reliability({ ers }: { ers: any }) {
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
    </section>
  )
}

function Failures({ deviations, failures }: { deviations: any; failures: Record<string, unknown> }) {
  void failures
  return (
    <section>
      <h2>Artifact Verification (deviation checks)</h2>
      {deviations && (
        <p>verified: <strong>{deviations.n_verified}</strong> — pass: <strong>{deviations.n_pass}</strong> / fail: <strong>{deviations.n_fail}</strong> (pending: {deviations.n_pending_no_artifact})</p>
      )}
      {deviations?.details_fail?.length > 0 && (
        <ul>{deviations.details_fail.map((f: any, i: number) => (
          <li key={i} style={{ color: '#cc0000' }}>{f.run_id}: {f.failed_checks.join(', ')}</li>
        ))}</ul>
      )}
      {(!deviations || deviations.n_fail === 0) && <p style={{ color: '#006600' }}>All artifacts pass deviation checks.</p>}
    </section>
  )
}