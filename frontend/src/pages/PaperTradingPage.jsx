// src/pages/PaperTradingPage.jsx
import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { getOpenTrades, getClosedTrades, getEquityCurve, getAccountSummary, getTradeStats, getMissedTrades } from '../paperTrades.js'
import PositionPanel from '../components/PositionPanel.jsx'
import '../App.css'

const CONFIG_META = {
  conservative: { targetPct: '7%',  maxDays: 10, color: '#4a7c59' },
  aggressive:   { targetPct: '15%', maxDays: 20, color: '#c8a84b' },
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function PaperStatCard({ label, value, sub, highlight }) {
  return (
    <div className="col">
      <div className="stat-card h-100">
        <div className="stat-label">{label}</div>
        <div
          className="stat-value"
          style={{
            fontSize: '1.4rem',
            ...(highlight === 'green' ? { color: '#4a7c59' } :
                highlight === 'red'   ? { color: '#8b4a4a' } : {})
          }}
        >
          {value ?? '...'}
        </div>
        {sub && (
          <div className="mt-1" style={{ fontSize: '0.75rem', color: '#5a6b58' }}>{sub}</div>
        )}
      </div>
    </div>
  )
}

// ── Custom tooltip for equity chart ───────────────────────────────────────────
function EquityTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="stat-card" style={{ padding: '10px 14px', fontSize: '0.82rem', minWidth: 180 }}>
      <div className="last-scanned-text mb-1">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} style={{ color: CONFIG_META[p.dataKey]?.color ?? '#888' }}>
          {p.dataKey}: <strong>${p.value?.toFixed(2)}</strong>
        </div>
      ))}
    </div>
  )
}

export default function PaperTradingPage() {
  const [tab, setTab]         = useState('open')
  const [openTrades, setOpen] = useState([])
  const [closed, setClosed]   = useState([])
  const [missed, setMissed]   = useState([])
  const [equity, setEquity]   = useState([])
  const [summary, setSummary] = useState([])
  const [stats, setStats]     = useState([])
  const [cfgFilter, setCfg]   = useState('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'SwingTrade | Paper Trading'
    Promise.all([
      getOpenTrades(),
      getClosedTrades(),
      getMissedTrades(),
      getEquityCurve(),
      getAccountSummary(),
      getTradeStats(),
    ]).then(([open, cl, ms, eq, sum, st]) => {
      setOpen(open)
      setClosed(cl)
      setMissed(ms)
      setEquity(eq)
      setSummary(sum)
      setStats(st)
      setLoading(false)
    })
  }, [])

  // ── Derived data ─────────────────────────────────────────────────────────
  const conOpen = openTrades.filter(t => t.config === 'conservative')
  const aggOpen = openTrades.filter(t => t.config === 'aggressive')

  const filteredClosed = cfgFilter === 'all'
    ? closed
    : closed.filter(t => t.config === cfgFilter)

  const filteredMissed = cfgFilter === 'all'
    ? missed
    : missed.filter(t => t.config === cfgFilter)

  // Missed stats — hypothetical only
  const missedWithPnl  = missed.filter(t => t.pnl_pct != null)
  const missedWins     = missedWithPnl.filter(t => t.pnl_pct > 0).length
  const missedWinRate  = missedWithPnl.length > 0
    ? ((missedWins / missedWithPnl.length) * 100).toFixed(0)
    : null
  const missedAvgPnl   = missedWithPnl.length > 0
    ? (missedWithPnl.reduce((a, t) => a + parseFloat(t.pnl_pct), 0) / missedWithPnl.length).toFixed(2)
    : null

  // Pivot equity rows into [{date, conservative, aggressive}, ...]
  const chartData = equity.reduce((acc, row) => {
    const existing = acc.find(r => r.date === row.date)
    if (existing) {
      existing[row.config] = parseFloat(row.equity)
    } else {
      acc.push({ date: row.date, [row.config]: parseFloat(row.equity) })
    }
    return acc
  }, [])

  function getSummary(config) {
    return summary.find(s => s.config === config) ?? {}
  }
  function getStats(config) {
    return stats.find(s => s.config === config) ?? {}
  }

  // ── Tab button ────────────────────────────────────────────────────────────
  function tabBtn(id, label) {
    const active = tab === id
    return (
      <button
        key={id}
        onClick={() => setTab(id)}
        style={{
          background:   active ? '#4a7c59' : 'transparent',
          color:        active ? '#fff' : '#5a6b58',
          border:       active ? 'none' : '1px solid #c8d4c0',
          borderRadius: '8px',
          padding:      '6px 16px',
          fontSize:     '0.82rem',
          fontWeight:   active ? 600 : 400,
          cursor:       'pointer',
          transition:   'all 0.15s ease',
        }}
      >
        {label}
      </button>
    )
  }

  if (loading) {
    return <p className="text-secondary p-4">Loading...</p>
  }

  return (
    <div>
      {/* ── Page header ── */}
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div>
          <h1 className="mb-1">Paper Trading</h1>
          <span className="last-scanned-text">
            52-Week High Momentum · Two independent $1,000 accounts
          </span>
        </div>
      </div>

      {/* ── Account summary stat cards ── */}
      {['conservative', 'aggressive'].map(cfg => {
        const sum       = getSummary(cfg)
        const st        = getStats(cfg)
        const equity_val = parseFloat(sum.current_equity ?? 1000)
        const pnl        = equity_val - 1000
        const pnlPositive = pnl >= 0

        return (
          <div key={cfg} className="mb-3">
            <div
              className="last-scanned-text mb-2"
              style={{ fontSize: '0.8rem', textTransform: 'capitalize', fontWeight: 600, color: CONFIG_META[cfg].color }}
            >
              {cfg} · Stop 2% · Target {CONFIG_META[cfg].targetPct} · Max {CONFIG_META[cfg].maxDays}d
            </div>
            <div className="row row-cols-2 row-cols-md-3 row-cols-lg-6 g-3">
              <PaperStatCard
                label="Account equity"
                value={`$${equity_val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                sub="Started at $1,000"
                highlight={pnlPositive ? 'green' : 'red'}
              />
              <PaperStatCard
                label="Total P&L"
                value={(pnlPositive ? '+' : '') + `$${pnl.toFixed(2)}`}
                sub={`${pnlPositive ? '+' : ''}${((pnl / 1000) * 100).toFixed(1)}% return`}
                highlight={pnlPositive ? 'green' : 'red'}
              />
              <PaperStatCard
                label="Win rate"
                value={st.win_rate_pct != null ? `${st.win_rate_pct}%` : 'N/A'}
                sub={`${st.wins ?? 0}W / ${st.losses ?? 0}L`}
                highlight="green"
              />
              <PaperStatCard
                label="Avg P&L"
                value={st.avg_pnl_pct != null
                  ? (st.avg_pnl_pct >= 0 ? '+' : '') + `${parseFloat(st.avg_pnl_pct).toFixed(2)}%`
                  : 'N/A'}
                sub={`${st.total_trades ?? 0} closed trades`}
              />
              <PaperStatCard
                label="Open slots"
                value={`${2 - (cfg === 'conservative' ? conOpen : aggOpen).length}/2`}
                sub={`$${parseFloat(sum.available_cash ?? 1000).toFixed(2)} available`}
              />
              <PaperStatCard
                label="Exit breakdown"
                value={st.total_trades ? `${st.target_exits ?? 0}T / ${st.stop_exits ?? 0}S / ${st.time_exits ?? 0}Ti` : 'N/A'}
                sub="Target / Stop / Time"
              />
            </div>
          </div>
        )
      })}

      {/* ── Tab nav ── */}
      <div className="d-flex gap-2 mt-4 mb-4" style={{ flexWrap: 'wrap' }}>
        {tabBtn('open',   'Open Positions')}
        {tabBtn('closed', 'Closed Trades')}
        {tabBtn('missed', 'Missed Trades')}
        {tabBtn('equity', 'Equity Curve')}
      </div>

      {/* ── OPEN POSITIONS ── */}
      {tab === 'open' && (
        <div className="row g-3">
          <div className="col-12 col-md-6">
            <PositionPanel
              config="conservative"
              trades={conOpen}
              targetPct={CONFIG_META.conservative.targetPct}
              maxDays={CONFIG_META.conservative.maxDays}
            />
          </div>
          <div className="col-12 col-md-6">
            <PositionPanel
              config="aggressive"
              trades={aggOpen}
              targetPct={CONFIG_META.aggressive.targetPct}
              maxDays={CONFIG_META.aggressive.maxDays}
            />
          </div>
        </div>
      )}

      {/* ── CLOSED TRADES ── */}
      {tab === 'closed' && (
        <div>
          <div className="d-flex gap-2 mb-3">
            {['all', 'conservative', 'aggressive'].map(f => (
              <button
                key={f}
                onClick={() => setCfg(f)}
                style={{
                  background:    cfgFilter === f ? '#4a7c59' : 'transparent',
                  color:         cfgFilter === f ? '#fff' : '#5a6b58',
                  border:        cfgFilter === f ? 'none' : '1px solid #c8d4c0',
                  borderRadius:  '8px',
                  padding:       '5px 14px',
                  fontSize:      '0.8rem',
                  cursor:        'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {f}
              </button>
            ))}
            <span className="last-scanned-text" style={{ alignSelf: 'center', marginLeft: 4 }}>
              {filteredClosed.length} trade{filteredClosed.length !== 1 ? 's' : ''}
            </span>
          </div>

          {filteredClosed.length === 0 ? (
            <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No closed trades yet.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="w-100 signals-table">
                <thead>
                  <tr>
                    <th>Config</th><th>Ticker</th><th>Signal</th>
                    <th>Entry</th><th>Exit</th><th>Days</th>
                    <th>P&amp;L %</th><th>P&amp;L $</th><th>RS</th><th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredClosed.map(t => {
                    const pos = (t.pnl_pct ?? 0) >= 0
                    return (
                      <tr key={t.id}>
                        <td>
                          <span style={{ fontSize: '0.72rem', color: CONFIG_META[t.config]?.color ?? '#888', fontWeight: 600, textTransform: 'capitalize' }}>
                            {t.config === 'conservative' ? 'Con' : 'Agg'}
                          </span>
                        </td>
                        <td className="ticker-cell">{t.ticker}</td>
                        <td className="text-secondary" style={{ fontSize: '0.8rem' }}>{t.signal_date}</td>
                        <td className="text-secondary">${t.entry_price?.toFixed(2)}</td>
                        <td className="text-secondary">${t.exit_price?.toFixed(2)}</td>
                        <td className="text-secondary">{t.days_held}</td>
                        <td className={pos ? 'rs-cell' : 'loss-cell'}>
                          {pos ? '+' : ''}{parseFloat(t.pnl_pct ?? 0).toFixed(2)}%
                        </td>
                        <td className={pos ? 'rs-cell' : 'loss-cell'}>
                          {pos ? '+' : ''}${parseFloat(t.pnl_dollars ?? 0).toFixed(2)}
                        </td>
                        <td className="rs-cell">{t.relative_strength?.toFixed(1)}</td>
                        <td className="text-secondary" style={{ textTransform: 'capitalize', fontSize: '0.82rem' }}>{t.exit_reason}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── MISSED TRADES ── */}
      {tab === 'missed' && (
        <div>
          {/* Missed stats summary */}
          <div className="stat-card mb-3" style={{ padding: '12px 16px' }}>
            <div className="d-flex gap-4 flex-wrap">
              <div>
                <div className="stat-label" style={{ fontSize: '0.72rem' }}>Total missed</div>
                <div style={{ fontWeight: 600, color: '#2c3a2c' }}>{missed.length}</div>
              </div>
              <div>
                <div className="stat-label" style={{ fontSize: '0.72rem' }}>Resolved</div>
                <div style={{ fontWeight: 600, color: '#2c3a2c' }}>{missedWithPnl.length}</div>
              </div>
              {missedWinRate && (
                <div>
                  <div className="stat-label" style={{ fontSize: '0.72rem' }}>Hypothetical win rate</div>
                  <div style={{ fontWeight: 600, color: '#4a7c59' }}>{missedWinRate}%</div>
                </div>
              )}
              {missedAvgPnl && (
                <div>
                  <div className="stat-label" style={{ fontSize: '0.72rem' }}>Hypothetical avg P&L</div>
                  <div style={{ fontWeight: 600, color: parseFloat(missedAvgPnl) >= 0 ? '#4a7c59' : '#8b4a4a' }}>
                    {parseFloat(missedAvgPnl) >= 0 ? '+' : ''}{missedAvgPnl}%
                  </div>
                </div>
              )}
              <div style={{ alignSelf: 'center', marginLeft: 'auto' }}>
                <span className="last-scanned-text" style={{ fontSize: '0.72rem' }}>
                  Hypothetical only — slots were full when these signals fired
                </span>
              </div>
            </div>
          </div>

          {/* Config filter */}
          <div className="d-flex gap-2 mb-3">
            {['all', 'conservative', 'aggressive'].map(f => (
              <button
                key={f}
                onClick={() => setCfg(f)}
                style={{
                  background:    cfgFilter === f ? '#4a7c59' : 'transparent',
                  color:         cfgFilter === f ? '#fff' : '#5a6b58',
                  border:        cfgFilter === f ? 'none' : '1px solid #c8d4c0',
                  borderRadius:  '8px',
                  padding:       '5px 14px',
                  fontSize:      '0.8rem',
                  cursor:        'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {f}
              </button>
            ))}
            <span className="last-scanned-text" style={{ alignSelf: 'center', marginLeft: 4 }}>
              {filteredMissed.length} signal{filteredMissed.length !== 1 ? 's' : ''}
            </span>
          </div>

          {filteredMissed.length === 0 ? (
            <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No missed signals yet.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="w-100 signals-table">
                <thead>
                  <tr>
                    <th>Config</th><th>Ticker</th><th>Signal</th>
                    <th>Entry</th><th>Stop</th><th>Target</th>
                    <th>Exit</th><th>Days</th><th>P&amp;L %</th>
                    <th>RS</th><th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMissed.map(t => {
                    const hasPnl = t.pnl_pct != null
                    const pos    = hasPnl && parseFloat(t.pnl_pct) >= 0
                    return (
                      <tr key={t.id}>
                        <td>
                          <span style={{ fontSize: '0.72rem', color: CONFIG_META[t.config]?.color ?? '#888', fontWeight: 600, textTransform: 'capitalize' }}>
                            {t.config === 'conservative' ? 'Con' : 'Agg'}
                          </span>
                        </td>
                        <td className="ticker-cell">{t.ticker}</td>
                        <td className="text-secondary" style={{ fontSize: '0.8rem' }}>{t.signal_date}</td>
                        <td className="text-secondary">
                          {t.entry_price ? `$${parseFloat(t.entry_price).toFixed(2)}` : <span style={{ color: '#888' }}>pending</span>}
                        </td>
                        <td className="loss-cell">
                          {t.stop_price ? `$${parseFloat(t.stop_price).toFixed(2)}` : '—'}
                        </td>
                        <td className="rs-cell">
                          {t.target_price ? `$${parseFloat(t.target_price).toFixed(2)}` : '—'}
                        </td>
                        <td className="text-secondary">
                          {t.exit_price ? `$${parseFloat(t.exit_price).toFixed(2)}` : <span style={{ color: '#c8a84b' }}>open</span>}
                        </td>
                        <td className="text-secondary">{t.days_held ?? '—'}</td>
                        <td className={hasPnl ? (pos ? 'rs-cell' : 'loss-cell') : 'text-secondary'}>
                          {hasPnl
                            ? `${pos ? '+' : ''}${parseFloat(t.pnl_pct).toFixed(2)}%`
                            : '—'}
                        </td>
                        <td className="rs-cell">{t.relative_strength?.toFixed(1)}</td>
                        <td className="text-secondary" style={{ textTransform: 'capitalize', fontSize: '0.82rem' }}>
                          {t.exit_reason ?? <span style={{ color: '#c8a84b' }}>in play</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── EQUITY CURVE ── */}
      {tab === 'equity' && (
        <div className="stat-card">
          {chartData.length === 0 ? (
            <p className="text-secondary" style={{ fontSize: '0.85rem' }}>
              No closed trades yet — equity curve will appear here once trades close.
            </p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={340}>
                <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 24 }}>
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#5a6b58', fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: '#c8d4c0' }}
                  />
                  <YAxis
                    tickFormatter={v => `$${v}`}
                    tick={{ fill: '#5a6b58', fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={80}
                  />
                  <Tooltip content={<EquityTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: '0.8rem', color: '#5a6b58', paddingTop: '8px' }}
                    formatter={val => <span style={{ textTransform: 'capitalize', color: CONFIG_META[val]?.color }}>{val}</span>}
                  />
                  <ReferenceLine y={1000} stroke="#c8d4c0" strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="conservative" stroke={CONFIG_META.conservative.color} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                  <Line type="monotone" dataKey="aggressive"   stroke={CONFIG_META.aggressive.color}   strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
              <div className="last-scanned-text mt-2" style={{ fontSize: '0.75rem' }}>
                Each account starts at $1,000 · Dynamic position sizing · Max 2 simultaneous positions
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}