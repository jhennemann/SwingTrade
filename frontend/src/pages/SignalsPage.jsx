import { useEffect, useState } from 'react'
import { supabase } from '../supabase.js'
import '../App.css'

const CONFIGS = ['conservative', 'aggressive']

function StatusBadge({ status }) {
  const styles = {
    open:   { background: '#1a2a1a', color: '#5a6b58' },
    closed: { background: '#1a1a2a', color: '#6a6a8a' },
    missed: { background: '#2a1a1a', color: '#a85c4a' },
  }
  const s = styles[status] ?? styles.missed
  return (
    <span style={{
      fontSize: '0.7rem',
      padding: '2px 8px',
      borderRadius: '10px',
      fontWeight: 600,
      letterSpacing: '0.04em',
      ...s,
    }}>
      {status.toUpperCase()}
    </span>
  )
}

export default function SignalsFeedPage() {
  const [config, setConfig] = useState('conservative')
  const [grouped, setGrouped] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'SwingTrade | Signals Feed'
    fetchSignals(config)
  }, [config])

  async function fetchSignals(cfg) {
    setLoading(true)

    const since = new Date()
    since.setDate(since.getDate() - 30)
    const sinceStr = since.toISOString().split('T')[0]

    const { data } = await supabase
      .from('paper_trades')
      .select('*')
      .eq('config', cfg)
      .gte('signal_date', sinceStr)
      .order('signal_date', { ascending: false })

    // Group by signal_date
    const groups = {}
    for (const trade of data ?? []) {
      const d = trade.signal_date
      if (!groups[d]) groups[d] = []
      groups[d].push(trade)
    }

    setGrouped(groups)
    setLoading(false)
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—'
    return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
    })
  }

  function pnlColor(pnl) {
    if (pnl == null) return '#8a9a8a'
    return pnl >= 0 ? '#5a6b58' : '#a85c4a'
  }

  return (
    <div>
      {/* ── Header ── */}
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div>
          <h1 className="mb-1">Signals Feed</h1>
          <span className="last-scanned-text">Last 30 days · 52-Week High Momentum</span>
        </div>

        {/* Config toggle */}
        <div className="view-toggle" style={{ marginTop: '4px' }}>
          {CONFIGS.map(c => (
            <button
              key={c}
              className={`toggle-btn ${config === c ? 'active' : ''}`}
              onClick={() => setConfig(c)}
            >
              {c === 'conservative' ? 'Conservative' : 'Aggressive'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-secondary">Loading...</p>
      ) : Object.keys(grouped).length === 0 ? (
        <p className="text-secondary">No signals in the last 30 days.</p>
      ) : (
        Object.entries(grouped).map(([date, trades]) => (
          <div key={date} className="mb-4">
            {/* Date header */}
            <div className="signals-date-header">{formatDate(date)}</div>

            <div className="stat-card" style={{ padding: '0' }}>
              <div style={{ overflowX: 'auto' }}>
                <table className="w-100 signals-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Status</th>
                      <th>RS</th>
                      <th>Entry</th>
                      <th>Stop</th>
                      <th>Target</th>
                      <th>Current</th>
                      <th>P&L</th>
                      <th>Days</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map(t => {
                      const isOpen = t.status === 'open'
                      const isClosed = t.status === 'closed'
                      const isMissed = t.status === 'missed'

                      return (
                        <tr key={t.id}>
                          <td className="ticker-cell">{t.ticker}</td>
                          <td><StatusBadge status={t.status} /></td>
                          <td className="rs-cell">{t.relative_strength?.toFixed(1) ?? '—'}</td>
                          <td className="text-secondary">
                            {t.entry_price != null ? `$${t.entry_price.toFixed(2)}` : '—'}
                          </td>
                          <td style={{ color: '#a85c4a' }}>
                            {t.stop_price != null ? `$${t.stop_price.toFixed(2)}` : '—'}
                          </td>
                          <td style={{ color: '#5a6b58' }}>
                            {t.target_price != null ? `$${t.target_price.toFixed(2)}` : '—'}
                          </td>
                          <td className="text-secondary">
                            {(isOpen || (isMissed && !t.exit_date)) && t.current_price != null
                              ? `$${t.current_price.toFixed(2)}`
                              : '—'}
                          </td>
                          <td>
                            {t.pnl_pct != null ? (
                              <span style={{ color: pnlColor(t.pnl_pct), fontWeight: 600 }}>
                                {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                              </span>
                            ) : (isOpen || (isMissed && !t.exit_date)) && t.entry_price != null && t.current_price != null ? (
                              (() => {
                                const pct = (t.current_price - t.entry_price) / t.entry_price * 100
                                return (
                                  <span style={{ color: pnlColor(pct), fontWeight: 600 }}>
                                    {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                                  </span>
                                )
                              })()
                            ) : '—'}
                          </td>
                          <td className="text-secondary">{t.days_held ?? '—'}</td>
                          <td className="text-secondary" style={{ fontSize: '0.8rem' }}>
                            {isClosed || isMissed ? (t.exit_reason ?? '—') : 'in play'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}