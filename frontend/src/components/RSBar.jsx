export default function RSBar({ value }) {
  const isNegative = (value ?? 0) < 0
  const width = Math.min(100, Math.max(0, Math.abs(value ?? 0)))
  return (
    <div className="d-flex align-items-center gap-2">
      <span style={{ minWidth: '34px', fontSize: '0.85rem', color: isNegative ? '#a85c4a' : '#2c3a2c' }}>
        {(value ?? 0).toFixed(1)}
      </span>
      <div
        style={{
          width: '80px',
          height: '4px',
          background: '#dde0db',
          borderRadius: '2px',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: `${width}%`,
            height: '100%',
            background: isNegative ? '#a85c4a' : '#4a7c59',
            borderRadius: '2px',
          }}
        />
      </div>
    </div>
  )
}