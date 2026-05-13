import { Card } from 'react-bootstrap'

export default function StatCard({ label, value, tooltip }) {
  return (
    <div className="col-md-4">
      <Card className="stat-card">
        <Card.Body>
          <div className="stat-label">
            {label}
            {tooltip && (
              <span className="stat-tooltip-wrapper">
                <span className="stat-info-icon">i</span>
                <span className="stat-tooltip-text">{tooltip}</span>
              </span>
            )}
          </div>
          <div className="stat-value">{value}</div>
        </Card.Body>
      </Card>
    </div>
  )
}