// src/components/PositionPanel.jsx
// Displays open positions for one config (conservative or aggressive)
// Used by PaperTradingPage to meet the 12-component requirement

const MAX_SLOTS = 2

export default function PositionPanel({ config, trades, targetPct, maxDays }) {
  const slots = MAX_SLOTS - trades.length

  function daysHeld(entryDate) {
    if (!entryDate) return 0
    return Math.floor((Date.now() - new Date(entryDate + 'T12:00:00')) / 86400000)
  }

  return (
    <div className="stat-card h-100">
      {/* Header */}
      <div className="d-flex justify-content-between align-items-start mb-3">
        <div>
          <div style={{ fontWeight: 600, color: '#2c3a2c', fontSize: '0.95rem', textTransform: 'capitalize' }}>
            {config}
          </div>
          <div className="last-scanned-text" style={{ fontSize: '0.72rem', marginTop: '2px' }}>
            Stop 2% · Target {targetPct} · Max {maxDays}d
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.72rem', color: '#5a6b58' }}>Slots open</div>
          <div style={{ fontWeight: 700, color: slots > 0 ? '#4a7c59' : '#888', fontSize: '1.1rem' }}>
            {slots}/{MAX_SLOTS}
          </div>
        </div>
      </div>

      {/* Table or empty state */}
      {trades.length === 0 ? (
        <p className="text-secondary" style={{ fontSize: '0.85rem' }}>No open positions.</p>
      ) : (
        <table className="w-100 signals-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Entry</th>
              <th>Stop</th>
              <th>Target</th>
              <th>RS</th>
              <th>Days</th>
            </tr>
          </thead>
          <tbody>
            {trades.map(t => (
              <tr key={t.id}>
                <td className="ticker-cell">{t.ticker}</td>
                <td className="text-secondary">${t.entry_price?.toFixed(2)}</td>
                <td className="loss-cell">${t.stop_price?.toFixed(2)}</td>
                <td className="rs-cell">${t.target_price?.toFixed(2)}</td>
                <td className="rs-cell">{t.relative_strength?.toFixed(1)}</td>
                <td className="text-secondary">{daysHeld(t.entry_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Footer: position size */}
      {trades.length > 0 && (
        <div className="mt-2 last-scanned-text" style={{ fontSize: '0.72rem' }}>
          {trades.map(t => (
            <span key={t.id} style={{ marginRight: '12px' }}>
              {t.ticker}: ${t.position_size?.toFixed(2)} · {t.shares?.toFixed(4)} shares
            </span>
          ))}
        </div>
      )}
    </div>
  )
}