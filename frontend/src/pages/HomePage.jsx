import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../supabase.js'
import WatchlistButton from '../components/WatchlistButton.jsx'
import '../App.css'

function DashStatCard({ label, value, sub, highlight }) {
  return (
    <div className="col">
      <div className="stat-card h-100">
        <div className="stat-label">{label}</div>
        <div
          className="stat-value"
          style={highlight === 'green' ? { color: '#4a7c59' } : undefined}
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

// Returns the next market open date after a given YYYY-MM-DD string
function nextMarketOpen(dateStr) {
  const d = new Date(dateStr + 'T12:00:00')
  d.setDate(d.getDate() + 1)
  // Skip weekends
  while (d.getDay() === 0 || d.getDay() === 6) {
    d.setDate(d.getDate() + 1)
  }
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function HomePage() {
  const [stats, setStats] = useState({
    totalSignals: null,
    todaySignals: null,
    lastScanDate: null,
    totalDaysScanned: null,
    avgSignalsPerDay: null,
    winRateRS50: null,
    avgPLRS50: null,
    winRateAll: null,
    avgPLAll: null,
  })

  const [latestSignals, setLatestSignals] = useState([])
  const [latestDate, setLatestDate] = useState(null)
  const [prevSignals, setPrevSignals] = useState([])
  const [prevDate, setPrevDate] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStats()
    fetchSignals()
    document.title = 'SwingTrade | Dashboard'
  }, [])

  async function fetchStats() {
    const { data: scanStats } = await supabase
      .from('scan_stats')
      .select('*')
      .single()

    const totalSignals     = scanStats?.total_signals ?? null
    const totalDaysScanned = scanStats?.total_days_scanned ?? null

    const { data: latestRow } = await supabase
      .from('signals')
      .select('last_date')
      .order('last_date', { ascending: false })
      .limit(1)

    const lastScanDate = latestRow?.[0]?.last_date ?? null

    const { count: todayCount } = await supabase
      .from('signals')
      .select('*', { count: 'exact', head: true })
      .eq('last_date', lastScanDate)
      .eq('has_signal_today', true)

    const avgSignalsPerDay =
      totalDaysScanned > 0 ? (totalSignals / totalDaysScanned).toFixed(1) : 0

    const { data: closedRS50 } = await supabase
      .from('signals')
      .select('win_loss')
      .eq('status', 'closed')
      .gt('relative_strength', 50)

    const rs50     = closedRS50 ?? []
    const winsRS50 = rs50.filter(s => (s.win_loss ?? 0) > 0).length
    const winRateRS50 = rs50.length > 0
      ? ((winsRS50 / rs50.length) * 100).toFixed(0) + '%' : 'N/A'
    const sumPLRS50 = rs50.reduce((acc, s) => acc + (s.win_loss ?? 0), 0)
    const avgPLRS50 = rs50.length > 0
      ? (sumPLRS50 >= 0 ? '+' : '') + ((sumPLRS50 / rs50.length) * 100).toFixed(2) + '%' : 'N/A'

    const { data: closedAll } = await supabase
      .from('signals')
      .select('win_loss')
      .eq('status', 'closed')

    const all     = closedAll ?? []
    const winsAll = all.filter(s => (s.win_loss ?? 0) > 0).length
    const winRateAll = all.length > 0
      ? ((winsAll / all.length) * 100).toFixed(0) + '%' : 'N/A'
    const sumPLAll = all.reduce((acc, s) => acc + (s.win_loss ?? 0), 0)
    const avgPLAll = all.length > 0
      ? (sumPLAll >= 0 ? '+' : '') + ((sumPLAll / all.length) * 100).toFixed(2) + '%' : 'N/A'

    setStats({
      totalSignals,
      todaySignals: todayCount,
      lastScanDate,
      totalDaysScanned,
      avgSignalsPerDay,
      winRateRS50,
      avgPLRS50,
      winRateAll,
      avgPLAll,
    })
  }

  async function fetchSignals() {
    setLoading(true)

    const { data: dateRows } = await supabase
      .from('signals')
      .select('last_date')
      .order('last_date', { ascending: false })
      .limit(100)

    const uniqueDates = [...new Set(dateRows?.map(r => r.last_date) ?? [])]
    const d0 = uniqueDates[0] ?? null
    const d1 = uniqueDates[1] ?? null

    if (d0) {
      const { data } = await supabase
        .from('signals')
        .select('ticker, relative_strength, rank')
        .eq('last_date', d0)
        .eq('has_signal_today', true)
        .order('rank', { ascending: true })

      setLatestSignals(data ?? [])
      setLatestDate(d0)
    }

    if (d1) {
      const { data } = await supabase
        .from('signals')
        .select('ticker, relative_strength, rank, buy_price, current_price')
        .eq('last_date', d1)
        .eq('has_signal_today', true)
        .order('rank', { ascending: true })

      setPrevSignals(data ?? [])
      setPrevDate(d1)
    }

    setLoading(false)
  }

  function timeSince(dateStr) {
    if (!dateStr) return ''
    const days = Math.floor((new Date() - new Date(dateStr + 'T12:00:00')) / 86400000)
    if (days === 0) return 'today'
    if (days === 1) return '1 day ago'
    return `${days} days ago`
  }

  function pnl(buy, current) {
    if (buy == null || current == null) return null
    return (current - buy) / buy
  }

  return (
    <div>

      {/* ── Header ── */}
      <div className="d-flex justify-content-between align-items-start mb-4">
        <div>
          <h1 className="mb-1">Dashboard</h1>
          <span className="last-scanned-text">
            Last scanned: {stats.lastScanDate ?? '...'}
            {stats.lastScanDate ? ` · 6:00 PM CT (${timeSince(stats.lastScanDate)})` : ''}
          </span>
        </div>
        <Link
          to="/signals/"
          className="btn btn-sm fw-semibold"
          style={{
            background: '#4a7c59',
            color: '#fff',
            borderRadius: '8px',
            fontSize: '0.8rem',
            padding: '7px 14px',
            textDecoration: 'none',
            marginTop: '4px',
          }}
        >
          View all signals →
        </Link>
      </div>

      {/* ── Stat cards ── */}
      <div className="row row-cols-2 row-cols-md-3 row-cols-lg-6 g-3 mb-4">
        <DashStatCard
          label="Latest signals"
          value={stats.todaySignals ?? '...'}
          sub="All signals today"
        />
        <DashStatCard
          label="Total signals"
          value={stats.totalSignals?.toLocaleString() ?? '...'}
          sub="All time"
        />
        <DashStatCard
          label="Days scanned"
          value={stats.totalDaysScanned ?? '...'}
          sub={`Avg ${stats.avgSignalsPerDay ?? '...'} / day`}
        />
        <DashStatCard
          label="Win rate (RS>50)"
          value={stats.winRateRS50 ?? '...'}
          sub={`vs ${stats.winRateAll ?? '...'} unfiltered`}
          highlight="green"
        />
        <DashStatCard
          label="Avg P&L (RS>50)"
          value={stats.avgPLRS50 ?? '...'}
          sub={`vs ${stats.avgPLAll ?? '...'} unfiltered`}
          highlight="green"
        />
        <DashStatCard
          label="Universe"
          value="517"
          sub="S&P 500 + NDX"
        />
      </div>

      {/* ── Two-panel signals row ── */}
      {loading ? (
        <p className="text-secondary">Loading...</p>
      ) : (
        <div className="row g-3 align-items-start">

          {/* ── Left: Buy at Open ── */}
          <div className="col-12 col-md-4">
            <div className="stat-card h-100">
              <div className="mb-3">
                <span style={{ fontWeight: 500, color: '#2c3a2c', fontSize: '0.95rem' }}>
                  {latestDate ? `Buy ${nextMarketOpen(latestDate)} at Open` : 'Latest Signals'}
                </span>
                <div className="last-scanned-text" style={{ fontSize: '0.75rem', marginTop: '2px' }}>
                  {latestDate ?? '...'}
                </div>
              </div>

              {latestSignals.length === 0 ? (
                <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No signals from the latest scan.</p>
              ) : (
                <table className="w-100 signals-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>RS</th>
                      <th scope="col"><span className="visually-hidden">Watchlist</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {latestSignals.map(s => (
                      <tr key={s.ticker}>
                        <td className="ticker-cell">{s.ticker}</td>
                        <td className="rs-cell">{s.relative_strength?.toFixed(1)}</td>
                        <td><WatchlistButton ticker={s.ticker} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* ── Right: In Play ── */}
          <div className="col-12 col-md-8">
            <div className="stat-card h-100">
              <div className="mb-3">
                <span style={{ fontWeight: 500, color: '#2c3a2c', fontSize: '0.95rem' }}>
                  In Play
                </span>
                <div className="last-scanned-text" style={{ fontSize: '0.75rem', marginTop: '2px' }}>
                  {prevDate ?? '...'}
                </div>
              </div>

              {prevSignals.length === 0 ? (
                <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No signals from the previous scan.</p>
              ) : (
                <table className="w-100 signals-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>RS</th>
                      <th>Buy Price</th>
                      <th>Current</th>
                      <th>P&amp;L</th>
                      <th scope="col"><span className="visually-hidden">Watchlist</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {prevSignals.map(s => {
                      const pl = pnl(s.buy_price, s.current_price)
                      return (
                        <tr key={s.ticker}>
                          <td className="ticker-cell">{s.ticker}</td>
                          <td className="rs-cell">{s.relative_strength?.toFixed(1)}</td>
                          <td className="text-secondary">
                            {s.buy_price != null ? `$${s.buy_price.toFixed(2)}` : '—'}
                          </td>
                          <td className="text-secondary">
                            {s.current_price != null ? `$${s.current_price.toFixed(2)}` : '—'}
                          </td>
                          <td>
                            {pl != null ? (
                              <span className={pl >= 0 ? 'rs-cell' : 'loss-cell'}>
                                {pl >= 0 ? '+' : ''}${((s.current_price - s.buy_price)).toFixed(2)}
                                {' '}
                                <span style={{ fontSize: '0.8em', color: '#5a6b58' }}>
                                  ({pl >= 0 ? '+' : ''}{(pl * 100).toFixed(2)}%)
                                </span>
                              </span>
                            ) : '—'}
                          </td>
                          <td><WatchlistButton ticker={s.ticker} /></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>

        </div>
      )}

    </div>
  )
}