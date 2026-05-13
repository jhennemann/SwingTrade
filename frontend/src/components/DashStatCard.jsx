export default function DashStatCard({ label, value, sub, highlight }) {
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
          <div className="mt-1" style={{ fontSize: '0.75rem', color: '#7a8a78' }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  )
}