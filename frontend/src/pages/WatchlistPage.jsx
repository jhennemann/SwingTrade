import { useEffect, useState } from 'react'
import { supabase } from '../supabase.js'
import WatchlistButton from '../components/WatchlistButton.jsx'
import '../App.css'

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState([])
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(false)
  const [sortBy, setSortBy] = useState('date')
  const [sortDir, setSortDir] = useState('desc')

  useEffect(() => {
    document.title = 'SwingTrade | Watchlist'
    const stored = JSON.parse(localStorage.getItem('watchlist') ?? '[]')
    setWatchlist(stored)
  }, [])

  useEffect(() => {
    if (watchlist.length > 0) fetchSignals()
    else setSignals([])
  }, [watchlist])

  async function fetchSignals() {
    setLoading(true)
    const { data } = await supabase
      .from('signals_with_trades')
      .select('*')
      .in('ticker', watchlist)
      .order('last_date', { ascending: false })

    const seen = new Set()
    const latest = data?.filter(s => {
      if (seen.has(s.ticker)) return false
      seen.add(s.ticker)
      return true
    }) ?? []

    setSignals(latest)
    setLoading(false)
  }

  function isOpen(exitDate) {
    if (!exitDate) return true
    return new Date(exitDate) > new Date()
  }

  function handleRemove(ticker) {
    const updated = watchlist.filter(t => t !== ticker)
    localStorage.setItem('watchlist', JSON.stringify(updated))
    setWatchlist(updated)
  }

  function handleSort(col) {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortDir('desc')
    }
  }

  function getSortedSignals() {
    return [...signals].sort((a, b) => {
      let valA, valB

      if (sortBy === 'date') {
        valA = new Date(a.last_date)
        valB = new Date(b.last_date)
      } else if (sortBy === 'ticker') {
        valA = a.ticker
        valB = b.ticker
        return sortDir === 'asc'
          ? valA.localeCompare(valB)
          : valB.localeCompare(valA)
      } else if (sortBy === 'rs') {
        valA = a.relative_strength ?? -999
        valB = b.relative_strength ?? -999
      } else if (sortBy === 'pl') {
        valA = isOpen(a.exit_date) ? -999 : (a.win_loss ?? -999)
        valB = isOpen(b.exit_date) ? -999 : (b.win_loss ?? -999)
      } else if (sortBy === 'buy_price') {
        valA = a.buy_price ?? -999
        valB = b.buy_price ?? -999
      }

      return sortDir === 'asc' ? valA - valB : valB - valA
    })
  }

  function SortHeader({ col, label }) {
    const active = sortBy === col
    const arrow = active ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''
    return (
      <th
        onClick={() => handleSort(col)}
        style={{
          cursor: 'pointer',
          userSelect: 'none',
          color: active ? '#4a7c59' : '#7a8a78',
          whiteSpace: 'nowrap',
        }}
      >
        {label}{arrow}
      </th>
    )
  }

  const sorted = getSortedSignals()

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1 className="mb-0">Watchlist</h1>
        <div className="d-flex align-items-center gap-3">
          {signals.length > 0 && (
            <span style={{ fontSize: '0.85rem', color: '#7a8a78' }}>
              {signals.length} ticker{signals.length !== 1 ? 's' : ''} · click column to sort
            </span>
          )}
          {watchlist.length > 0 && (
            <button
              onClick={() => {
                localStorage.setItem('watchlist', '[]')
                setWatchlist([])
              }}
              style={{
                background: 'transparent',
                border: '1px solid #dde0db',
                borderRadius: '8px',
                color: '#a85c4a',
                fontSize: '0.8rem',
                padding: '4px 12px',
                cursor: 'pointer',
              }}
            >
              Clear all
            </button>
          )}
        </div>
      </div>

      {watchlist.length === 0 ? (
        <p className="text-secondary">
          No tickers bookmarked yet. Go to the Signals page and click the bookmark icon to add stocks.
        </p>
      ) : loading ? (
        <p className="text-secondary">Loading...</p>
      ) : (
        <table className="w-100 signals-table">
          <thead>
            <tr>
              <SortHeader col="ticker" label="Ticker" />
              <SortHeader col="date" label="Signal Date" />
              <SortHeader col="rs" label="Relative Strength" />
              <SortHeader col="buy_price" label="Buy Price" />
              <SortHeader col="pl" label="P&L" />
              <th style={{ color: '#7a8a78' }}>Exit Reason</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(s => (
              <tr key={s.ticker}>
                <td className="ticker-cell">{s.ticker}</td>
                <td className="text-secondary">{s.last_date}</td>
                <td className="rs-cell">{s.relative_strength?.toFixed(2)}</td>
                <td className="text-secondary">
                  {s.buy_price != null ? `$${s.buy_price.toFixed(2)}` : '—'}
                </td>
                <td className={
                  isOpen(s.exit_date) ? 'open-cell'
                  : s.win_loss > 0 ? 'rs-cell'
                  : 'loss-cell'
                }>
                  {isOpen(s.exit_date) ? 'Open' : `${(s.win_loss * 100).toFixed(2)}%`}
                </td>
                <td className="text-secondary">{s.exit_reason ?? '—'}</td>
                <td>
                  <WatchlistButton ticker={s.ticker} onRemove={() => handleRemove(s.ticker)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}