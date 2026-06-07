import { useEffect, useState } from 'react'
import { supabase } from '../supabase.js'
import '../App.css'

function StatCard({ label, value, sub, color }) {
  return (
    <div className="col">
      <div className="stat-card h-100">
        <div className="stat-label">{label}</div>
        <div
          className="stat-value"
          style={color ? { color } : undefined}
        >
          {value ?? '...'}
        </div>
        {sub && (
          <div className="mt-1" style={{ fontSize: '0.75rem', color: '#5a6b58' }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  )
}

function AccountPanel({ config, summary, allTrades }) {
  const label = config === 'aggressive' ? 'Aggressive' : 'Conservative'
  const equity = summary?.current_equity
  const startingEquity = summary?.starting_equity ?? 1000
  const equityChange = equity != null ? equity - startingEquity : null
  const equityChangePct = equityChange != null ? (equityChange / startingEquity) * 100 : null
  const openSlots = summary?.open_slots ?? '...'
  const closedPnl = summary?.closed_pnl

  // Include closed + missed trades that have pnl_pct for stats
  const scoredTrades = allTrades.filter(
    t => t.config === config && (t.status === 'closed' || t.status === 'missed') && t.pnl_pct != null
  )
  const totalTrades = scoredTrades.length
  const wins = scoredTrades.filter(t => t.pnl_pct > 0).length
  const winRate = totalTrades > 0 ? (wins / totalTrades) * 100 : null
  const avgPnl = totalTrades > 0
    ? scoredTrades.reduce((sum, t) => sum + t.pnl_pct, 0) / totalTrades
    : null

  // Compounded $1,000 across all scored trades sorted by entry date
  const sorted = [...scoredTrades].sort((a, b) => (a.entry_date ?? '').localeCompare(b.entry_date ?? ''))
  const compounded = sorted.reduce((acc, t) => acc * (1 + t.pnl_pct / 100), 1000)

  const POS = '#5a6b58'
  const NEG = '#a85c4a'

  return (
    <div className="stat-card h-100">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <span style={{ fontWeight: 600, fontSize: '0.95rem', color: '#2c3a2c' }}>
          {label}
        </span>
        <span
          style={{
            fontSize: '0.7rem',
            padding: '2px 8px',
            borderRadius: '20px',
            background: config === 'aggressive' ? '#2a1a1a' : '#1a2a1a',
            color: config === 'aggressive' ? '#a85c4a' : '#5a6b58',
            fontWeight: 600,
            letterSpacing: '0.05em',
          }}
        >
          {label.toUpperCase()}
        </span>
      </div>

      <div className="row g-2">
        <div className="col-6">
          <div style={{ fontSize: '0.72rem', color: '#5a6b58', marginBottom: '2px' }}>Current Equity</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#e8f0e8' }}>
            {equity != null ? `$${equity.toFixed(2)}` : '...'}
          </div>
          {equityChangePct != null && (
            <div style={{ fontSize: '0.75rem', color: equityChangePct >= 0 ? POS : NEG }}>
              {equityChangePct >= 0 ? '+' : ''}{equityChangePct.toFixed(2)}%
            </div>
          )}
        </div>
        <div className="col-6">
          <div style={{ fontSize: '0.72rem', color: '#5a6b58', marginBottom: '2px' }}>Closed P&L</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: (closedPnl ?? 0) >= 0 ? POS : NEG }}>
            {closedPnl != null ? `${closedPnl >= 0 ? '+' : ''}$${closedPnl.toFixed(2)}` : '...'}
          </div>
        </div>
        <div className="col-6">
          <div style={{ fontSize: '0.72rem', color: '#5a6b58', marginBottom: '2px' }}>Win Rate</div>
          <div style={{ fontSize: '1.0rem', fontWeight: 600, color: winRate != null ? POS : '#e8f0e8' }}>
            {winRate != null ? `${winRate.toFixed(0)}%` : totalTrades === 0 ? 'No trades' : '...'}
          </div>
          {totalTrades > 0 && (
            <div style={{ fontSize: '0.7rem', color: '#5a6b58' }}>incl. missed</div>
          )}
        </div>
        <div className="col-6">
          <div style={{ fontSize: '0.72rem', color: '#5a6b58', marginBottom: '2px' }}>Avg P&L</div>
          <div style={{ fontSize: '1.0rem', fontWeight: 600, color: (avgPnl ?? 0) >= 0 ? POS : NEG }}>
            {avgPnl != null ? `${avgPnl >= 0 ? '+' : ''}${avgPnl.toFixed(2)}%` : totalTrades === 0 ? '—' : '...'}
          </div>
          {totalTrades > 0 && (
            <div style={{ fontSize: '0.7rem', color: '#5a6b58' }}>incl. missed</div>
          )}
        </div>
        <div className="col-6">
          <div style={{ fontSize: '0.72rem', color: '#5a6b58', marginBottom: '2px' }}>Open Slots</div>
          <div style={{ fontSize: '1.0rem', fontWeight: 600, color: '#e8f0e8' }}>
            {openSlots} / 2
          </div>
        </div>
        <div className="col-6">
          <div style={{ fontSize: '0.72rem', color: '#5a6b58', marginBottom: '2px' }}>$1,000 Compounded</div>
          <div style={{ fontSize: '1.0rem', fontWeight: 600, color: compounded >= 1000 ? POS : NEG }}>
            {totalTrades > 0 ? `$${compounded.toFixed(2)}` : '—'}
          </div>
        </div>
      </div>
    </div>
  )
}

export default function HomePage() {
  const [summaries, setSummaries] = useState({ aggressive: null, conservative: null })

  const [openTrades, setOpenTrades] = useState([])
  const [closedTrades, setClosedTrades] = useState([])
  const [allTrades, setAllTrades] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAll()
    document.title = 'SwingTrade | Dashboard'
  }, [])

  async function fetchAll() {
    setLoading(true)

    const [summaryRes, openRes, closedRes, allRes] = await Promise.all([
      supabase.from('paper_account_summary').select('*'),
      supabase.from('paper_trades').select('*').eq('status', 'open').order('entry_date', { ascending: false }),
      supabase.from('paper_trades').select('*').eq('status', 'closed').order('exit_date', { ascending: false }).limit(10),
      supabase.from('paper_trades').select('id,config,status,pnl_pct,entry_date').in('status', ['closed', 'missed']),
    ])

    const summaryData = summaryRes.data ?? []

    setSummaries({
      aggressive: summaryData.find(r => r.config === 'aggressive') ?? null,
      conservative: summaryData.find(r => r.config === 'conservative') ?? null,
    })
    setOpenTrades(openRes.data ?? [])
    setClosedTrades(closedRes.data ?? [])
    setAllTrades(allRes.data ?? [])
    setLoading(false)
  }

  function formatDate(dateStr) {
    if (!dateStr) return '—'
    return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  function timeSince(dateStr) {
    if (!dateStr) return ''
    const days = Math.floor((new Date() - new Date(dateStr + 'T12:00:00')) / 86400000)
    if (days === 0) return 'today'
    if (days === 1) return '1 day ago'
    return `${days} days ago`
  }

  // Most recent signal date from open or closed trades
  const allDates = [...openTrades, ...closedTrades]
    .map(t => t.signal_date)
    .filter(Boolean)
    .sort()
    .reverse()
  const lastScanDate = allDates[0] ?? null

  return (
    <div>

      {/* ── Header ── */}
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div>
          <h1 className="mb-1">Dashboard</h1>
          <span className="last-scanned-text">
            Last scanned: {lastScanDate ?? '...'}
            {lastScanDate ? ` · 6:00 PM CT (${timeSince(lastScanDate)})` : ''}
          </span>
        </div>
        <div
          style={{
            fontSize: '0.75rem',
            padding: '5px 12px',
            borderRadius: '8px',
            background: '#1a2a1a',
            color: '#4a7c59',
            fontWeight: 600,
            border: '1px solid #2a3a2a',
            marginTop: '4px',
          }}
        >
          52-Week High Momentum · Live Paper Trading
        </div>
      </div>

      {/* ── Strategy stat cards ── */}
      <div className="row row-cols-2 row-cols-md-4 g-3 mb-4">
        <StatCard
          label="Backtest Win Rate (RS>50)"
          value="26.9%"
          sub="197 trades, 2020–2025"
          color="#22c55e"
        />
        <StatCard
          label="Backtest Avg P&L (RS>50)"
          value="+2.51%"
          sub="vs +0.60% unfiltered"
          color="#22c55e"
        />
        <StatCard
          label="RS Filter"
          value="≥ 50"
          sub="Relative strength vs SPY"
        />
        <StatCard
          label="Universe"
          value="517"
          sub="S&P 500 + NDX 100"
        />
      </div>

      {loading ? (
        <p className="text-secondary">Loading...</p>
      ) : (
        <>
          {/* ── Account panels ── */}
          <div className="row g-3 mb-4">
            <div className="col-12 col-md-6">
              <AccountPanel
                config="conservative"
                summary={summaries.conservative}
                allTrades={allTrades}
              />
            </div>
            <div className="col-12 col-md-6">
              <AccountPanel
                config="aggressive"
                summary={summaries.aggressive}
                allTrades={allTrades}
              />
            </div>
          </div>

          {/* ── Open Positions ── */}
          <div className="stat-card mb-4">
            <div className="mb-3" style={{ fontWeight: 600, fontSize: '0.95rem', color: '#2c3a2c' }}>
              Open Positions
            </div>
            {openTrades.length === 0 ? (
              <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No open positions.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="w-100 signals-table">
                  <thead>
                    <tr>
                      <th>Config</th>
                      <th>Ticker</th>
                      <th>Entry</th>
                      <th>Stop</th>
                      <th>Target</th>
                      <th>RS</th>
                      <th>Signal Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {openTrades.map(t => (
                      <tr key={t.id}>
                        <td>
                          <span style={{
                            fontSize: '0.7rem',
                            padding: '1px 6px',
                            borderRadius: '10px',
                            background: t.config === 'aggressive' ? '#2a1a1a' : '#1a2a1a',
                            color: t.config === 'aggressive' ? '#a85c4a' : '#5a6b58',
                            fontWeight: 600,
                          }}>
                            {t.config === 'aggressive' ? 'AGG' : 'CON'}
                          </span>
                        </td>
                        <td className="ticker-cell">{t.ticker}</td>
                        <td className="text-secondary">${t.entry_price?.toFixed(2) ?? '—'}</td>
                        <td style={{ color: '#a85c4a' }}>${t.stop_price?.toFixed(2) ?? '—'}</td>
                        <td style={{ color: '#5a6b58' }}>${t.target_price?.toFixed(2) ?? '—'}</td>
                        <td className="rs-cell">{t.relative_strength?.toFixed(1) ?? '—'}</td>
                        <td className="text-secondary">{formatDate(t.signal_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Recent Closed Trades ── */}
          <div className="stat-card">
            <div className="mb-3" style={{ fontWeight: 600, fontSize: '0.95rem', color: '#2c3a2c' }}>
              Recent Closed Trades
            </div>
            {closedTrades.length === 0 ? (
              <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No closed trades yet.</p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="w-100 signals-table">
                  <thead>
                    <tr>
                      <th>Config</th>
                      <th>Ticker</th>
                      <th>Entry</th>
                      <th>Exit</th>
                      <th>P&L</th>
                      <th>Days</th>
                      <th>Reason</th>
                      <th>Exit Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closedTrades.map(t => (
                      <tr key={t.id}>
                        <td>
                          <span style={{
                            fontSize: '0.7rem',
                            padding: '1px 6px',
                            borderRadius: '10px',
                            background: t.config === 'aggressive' ? '#2a1a1a' : '#1a2a1a',
                            color: t.config === 'aggressive' ? '#a85c4a' : '#5a6b58',
                            fontWeight: 600,
                          }}>
                            {t.config === 'aggressive' ? 'AGG' : 'CON'}
                          </span>
                        </td>
                        <td className="ticker-cell">{t.ticker}</td>
                        <td className="text-secondary">${t.entry_price?.toFixed(2) ?? '—'}</td>
                        <td className="text-secondary">${t.exit_price?.toFixed(2) ?? '—'}</td>
                        <td>
                          <span style={{ color: (t.pnl_pct ?? 0) >= 0 ? '#5a6b58' : '#a85c4a', fontWeight: 600 }}>
                            {t.pnl_pct != null ? `${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%` : '—'}
                          </span>
                        </td>
                        <td className="text-secondary">{t.days_held ?? '—'}</td>
                        <td className="text-secondary" style={{ fontSize: '0.8rem' }}>
                          {t.exit_reason ?? '—'}
                        </td>
                        <td className="text-secondary">{formatDate(t.exit_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}