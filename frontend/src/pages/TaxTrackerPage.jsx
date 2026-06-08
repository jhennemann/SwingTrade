import { useEffect, useState } from 'react'
import { supabase } from '../supabase.js'
import '../App.css'

const CURRENT_YEAR = new Date().getFullYear()

function StatCard({ label, value, sub, color }) {
  return (
    <div className="col">
      <div className="stat-card h-100">
        <div className="stat-label">{label}</div>
        <div className="stat-value" style={color ? { color, fontSize: '1.4rem' } : { fontSize: '1.4rem' }}>
          {value ?? '...'}
        </div>
        {sub && (
          <div className="mt-1" style={{ fontSize: '0.75rem', color: '#5a6b58' }}>{sub}</div>
        )}
      </div>
    </div>
  )
}

export default function TaxTrackerPage() {
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(true)
  const [taxRate, setTaxRate] = useState(28)
  const [cfgFilter, setCfgFilter] = useState('all')

  useEffect(() => {
    document.title = 'SwingTrade | Tax Tracker'
    fetchTrades()
  }, [])

  async function fetchTrades() {
    setLoading(true)

    const yearStart = `${CURRENT_YEAR}-01-01`
    const yearEnd   = `${CURRENT_YEAR}-12-31`

    const { data } = await supabase
      .from('paper_trades')
      .select('id, config, ticker, exit_date, pnl_dollars, pnl_pct, entry_price, exit_price, exit_reason')
      .eq('status', 'closed')
      .not('pnl_dollars', 'is', null)
      .gte('exit_date', yearStart)
      .lte('exit_date', yearEnd)
      .order('exit_date', { ascending: false })

    setTrades(data ?? [])
    setLoading(false)
  }

  const filtered = cfgFilter === 'all'
    ? trades
    : trades.filter(t => t.config === cfgFilter)

  const netPnl     = filtered.reduce((sum, t) => sum + parseFloat(t.pnl_dollars ?? 0), 0)
  const taxOwed    = netPnl > 0 ? netPnl * (taxRate / 100) : 0
  const afterTax   = netPnl - taxOwed
  const totalWins  = filtered.filter(t => parseFloat(t.pnl_dollars ?? 0) > 0).length
  const totalLoss  = filtered.filter(t => parseFloat(t.pnl_dollars ?? 0) < 0).length

  function formatDate(dateStr) {
    if (!dateStr) return '—'
    return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    })
  }

  function dollar(val) {
    const n = parseFloat(val ?? 0)
    return `${n >= 0 ? '+' : '-'}$${Math.abs(n).toFixed(2)}`
  }

  return (
    <div>
      {/* ── Header ── */}
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div>
          <h1 className="mb-1">Tax Tracker</h1>
          <span className="last-scanned-text">
            {CURRENT_YEAR} · Closed trades only · Short-term capital gains
          </span>
        </div>
      </div>

      {/* ── Tax rate slider ── */}
      <div className="stat-card mb-4">
        <div className="d-flex justify-content-between align-items-center mb-2">
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#2c3a2c' }}>
            Tax Rate: {taxRate}%
          </span>
          <span style={{ fontSize: '0.75rem', color: '#5a6b58' }}>
            Short-term gains taxed as ordinary income · Federal + Wisconsin state
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={50}
          step={1}
          value={taxRate}
          onChange={e => setTaxRate(Number(e.target.value))}
          style={{ width: '100%', accentColor: '#4a7c59', cursor: 'pointer' }}
        />
        <div className="d-flex justify-content-between mt-1" style={{ fontSize: '0.72rem', color: '#5a6b58' }}>
          <span>0%</span>
          <span>~22% federal only</span>
          <span>~28% fed + WI state</span>
          <span>50%</span>
        </div>
      </div>

      {/* ── Config filter ── */}
      <div className="d-flex gap-2 mb-4">
        {['all', 'conservative', 'aggressive'].map(f => (
          <button
            key={f}
            onClick={() => setCfgFilter(f)}
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
      </div>

      {loading ? (
        <p className="text-secondary">Loading...</p>
      ) : (
        <>
          {/* ── Stat cards ── */}
          <div className="row row-cols-2 row-cols-md-4 g-3 mb-4">
            <StatCard
              label="Net Realized P&L"
              value={dollar(netPnl)}
              sub={`${filtered.length} closed trades`}
              color={netPnl >= 0 ? '#5a6b58' : '#a85c4a'}
            />
            <StatCard
              label="Estimated Tax Owed"
              value={netPnl > 0 ? `$${taxOwed.toFixed(2)}` : '$0.00'}
              sub={netPnl <= 0 ? 'No tax on net loss' : `At ${taxRate}% rate`}
              color={taxOwed > 0 ? '#a85c4a' : '#5a6b58'}
            />
            <StatCard
              label="After-Tax P&L"
              value={dollar(afterTax)}
              sub="Net P&L minus estimated tax"
              color={afterTax >= 0 ? '#5a6b58' : '#a85c4a'}
            />
            <StatCard
              label="Win / Loss"
              value={`${totalWins}W / ${totalLoss}L`}
              sub={`${filtered.length > 0 ? ((totalWins / filtered.length) * 100).toFixed(0) : 0}% win rate`}
              color="#5a6b58"
            />
          </div>

          {/* ── Per-trade breakdown ── */}
          <div className="stat-card">
            <div className="mb-3" style={{ fontWeight: 600, fontSize: '0.95rem', color: '#2c3a2c' }}>
              Per-Trade Breakdown
            </div>

            {filtered.length === 0 ? (
              <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No closed trades with P&L data for {CURRENT_YEAR}.</p>
            ) : (
              <>
                <div style={{ overflowX: 'auto' }}>
                  <table className="w-100 signals-table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Config</th>
                        <th>Exit Date</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>Reason</th>
                        <th>P&L $</th>
                        <th>Tax Est.</th>
                        <th>After-Tax</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map(t => {
                        const pnl      = parseFloat(t.pnl_dollars ?? 0)
                        const tax      = pnl > 0 ? pnl * (taxRate / 100) : 0
                        const afterTaxRow = pnl - tax
                        const pos      = pnl >= 0

                        return (
                          <tr key={t.id}>
                            <td className="ticker-cell">{t.ticker}</td>
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
                            <td className="text-secondary">{formatDate(t.exit_date)}</td>
                            <td className="text-secondary">
                              {t.entry_price != null ? `$${parseFloat(t.entry_price).toFixed(2)}` : '—'}
                            </td>
                            <td className="text-secondary">
                              {t.exit_price != null ? `$${parseFloat(t.exit_price).toFixed(2)}` : '—'}
                            </td>
                            <td className="text-secondary" style={{ fontSize: '0.8rem', textTransform: 'capitalize' }}>
                              {t.exit_reason ?? '—'}
                            </td>
                            <td style={{ color: pos ? '#5a6b58' : '#a85c4a', fontWeight: 600 }}>
                              {dollar(pnl)}
                            </td>
                            <td style={{ color: tax > 0 ? '#a85c4a' : '#5a6b58' }}>
                              {tax > 0 ? `-$${tax.toFixed(2)}` : '$0.00'}
                            </td>
                            <td style={{ color: afterTaxRow >= 0 ? '#5a6b58' : '#a85c4a', fontWeight: 600 }}>
                              {dollar(afterTaxRow)}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>

                    {/* Totals row */}
                    <tfoot>
                      <tr style={{ borderTop: '1px solid #333' }}>
                        <td colSpan={6} style={{ fontWeight: 600, color: '#2c3a2c', fontSize: '0.85rem', paddingTop: '10px' }}>
                          Total
                        </td>
                        <td style={{ color: netPnl >= 0 ? '#5a6b58' : '#a85c4a', fontWeight: 700, paddingTop: '10px' }}>
                          {dollar(netPnl)}
                        </td>
                        <td style={{ color: taxOwed > 0 ? '#a85c4a' : '#5a6b58', fontWeight: 700, paddingTop: '10px' }}>
                          {taxOwed > 0 ? `-$${taxOwed.toFixed(2)}` : '$0.00'}
                        </td>
                        <td style={{ color: afterTax >= 0 ? '#5a6b58' : '#a85c4a', fontWeight: 700, paddingTop: '10px' }}>
                          {dollar(afterTax)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                <div className="mt-3" style={{ fontSize: '0.75rem', color: '#5a6b58' }}>
                  ⚠ Estimates only — consult a tax professional for actual tax liability.
                  Short-term gains (held &lt; 1 year) are taxed as ordinary income.
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}