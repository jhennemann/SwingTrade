export default function StatusPill({ status }) {
  const isOpen = status === 'Open'
  return (
    <span
      className="badge rounded-pill"
      style={{
        background: isOpen ? '#e0ede5' : '#f4f5f3',
        color: isOpen ? '#4a7c59' : '#7a8a78',
        border: `1px solid ${isOpen ? '#b8d9c4' : '#dde0db'}`,
        fontSize: '0.72rem',
        fontWeight: 500,
        padding: '3px 10px',
      }}
    >
      {status ?? 'Open'}
    </span>
  )
}