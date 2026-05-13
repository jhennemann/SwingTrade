import '../App.css'
import WatchlistButton from './WatchlistButton.jsx'

const fmt = n => (n != null ? `$${Number(n).toFixed(2)}` : '—')

const calcStop   = buy => buy != null ? buy * 0.98 : null
const calcTarget = buy => buy != null ? buy * 1.07 : null

function RSBar({ value }) {
  const width = Math.min(100, Math.max(0, value ?? 0))
  return (
    <div className="d-flex align-items-center gap-2">
      <span style={{ minWidth: '34px', fontSize: '0.85rem', color: '#2c3a2c' }}>
        {(value ?? 0).toFixed(1)}
      </span>
      <div style={{ width: '70px', height: '4px', background: '#dde0db', borderRadius: '2px', overflow: 'hidden', flexShrink: 0 }}>
        <div style={{ width: `${width}%`, height: '100%', background: '#4a7c59', borderRadius: '2px' }} />
      </div>
    </div>
  )
}

function PnLCell({ value }) {
  if (value == null) return <td className="text-secondary">—</td>
  const pct = (value * 100).toFixed(2)
  return (
    <td className={value > 0 ? 'rs-cell' : 'loss-cell'} style={{ whiteSpace: 'nowrap' }}>
      {value > 0 ? '+' : ''}{pct}%
    </td>
  )
}

function OpenRow({ s }) {
  const pnl = s.current_price != null && s.buy_price != null
    ? (s.current_price - s.buy_price) / s.buy_price
    : null

  return (
    <tr>
      <td className="ticker-cell">{s.ticker}</td>
      <td><RSBar value={s.relative_strength ?? 0} /></td>
      <td className="text-secondary" style={{ whiteSpace: 'nowrap' }}>{fmt(s.buy_price)}</td>
      <td style={{ color: '#a85c4a', whiteSpace: 'nowrap' }}>{fmt(calcStop(s.buy_price))}</td>
      <td className="rs-cell" style={{ whiteSpace: 'nowrap' }}>{fmt(calcTarget(s.buy_price))}</td>
      <td className="text-secondary" style={{ whiteSpace: 'nowrap' }}>{fmt(s.current_price)}</td>
      <PnLCell value={pnl} />
      <td><WatchlistButton ticker={s.ticker} /></td>
    </tr>
  )
}

function ClosedRow({ s }) {
  return (
    <tr>
      <td className="ticker-cell">{s.ticker}</td>
      <td><RSBar value={s.relative_strength ?? 0} /></td>
      <td className="text-secondary" style={{ whiteSpace: 'nowrap' }}>{fmt(s.buy_price)}</td>
      <td className="text-secondary" style={{ whiteSpace: 'nowrap' }}>{fmt(s.exit_price)}</td>
      <PnLCell value={s.win_loss} />
      <td className="text-secondary">{s.days_held ?? '—'}</td>
      <td className="text-secondary">{s.exit_reason ?? '—'}</td>
      <td><WatchlistButton ticker={s.ticker} /></td>
    </tr>
  )
}

export default function SignalTable({ signals, sortSignals }) {
  const sorted = sortSignals(signals)
  const open   = sorted.filter(s => s.status === 'open')
  const closed = sorted.filter(s => s.status === 'closed')

  return (
    <>
      {open.length > 0 && (
        <>
          <p className="signals-sub-header">Open</p>
          <div className="table-responsive">
            <table className="w-100 signals-table mb-4">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>RS</th>
                  <th>Entry</th>
                  <th>Stop</th>
                  <th>Target</th>
                  <th>Current</th>
                  <th>P&amp;L</th>
                  <th scope="col"><span className="visually-hidden">Watchlist</span></th>
                </tr>
              </thead>
              <tbody>
                {open.map(s => <OpenRow key={`${s.ticker}-${s.last_date}`} s={s} />)}
              </tbody>
            </table>
          </div>
        </>
      )}

      {closed.length > 0 && (
        <>
          <p className="signals-sub-header">Closed</p>
          <div className="table-responsive">
            <table className="w-100 signals-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>RS</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>P&amp;L</th>
                  <th>Days Held</th>
                  <th>Exit Reason</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {closed.map(s => <ClosedRow key={`${s.ticker}-${s.last_date}`} s={s} />)}
              </tbody>
            </table>
          </div>
        </>
      )}

      {open.length === 0 && closed.length === 0 && (
        <p className="text-secondary" style={{ fontSize: '0.9rem' }}>No signals for this date.</p>
      )}
    </>
  )
}