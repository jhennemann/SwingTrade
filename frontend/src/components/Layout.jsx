import { Link, Outlet, useLocation } from 'react-router-dom'
import '../App.css'
import WelcomeModal from './WelcomeModal.jsx'
import { useEffect, useRef, useState } from 'react'

const NAV_LINKS = [
  { to: '/', label: 'Home' },
  { to: '/signals/', label: 'Signals' },
  { to: '/watchlist/', label: 'Watchlist' },
  { to: '/about/', label: 'About' },
]

export default function Layout() {
  const location = useLocation()
  const navRef = useRef(null)
  const linkRefs = useRef({})
  const [pillStyle, setPillStyle] = useState({ width: 0, left: 0, opacity: 0 })

  useEffect(() => {
    const activePath = NAV_LINKS.find(l => l.to === location.pathname)?.to
    if (!activePath || !linkRefs.current[activePath] || !navRef.current) return

    const linkEl = linkRefs.current[activePath]
    const navEl = navRef.current
    const linkRect = linkEl.getBoundingClientRect()
    const navRect = navEl.getBoundingClientRect()

    setPillStyle({
      width: linkRect.width,
      left: linkRect.left - navRect.left,
      opacity: 1,
    })
  }, [location.pathname])

  return (
    <div>
      <WelcomeModal />
      <header>
      <nav className="navbar navbar-dark bg-dark main-nav">
        <Link to="/" className="navbar-brand fw-bold d-flex align-items-center gap-2">
          <img src="/p44/chart2.svg" alt="SwingTrade logo" style={{ width: '24px', height: '24px' }} />
          SwingTrade
        </Link>

        <div className="d-flex gap-4 position-relative" ref={navRef}>

          {/* sliding pill */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              transform: 'translateY(-50%)',
              height: '28px',
              borderRadius: '999px',
              background: '#ffffff20',
              transition: 'left 0.25s ease, width 0.25s ease, opacity 0.2s ease',
              pointerEvents: 'none',
              left: pillStyle.left,
              width: pillStyle.width,
              opacity: pillStyle.opacity,
            }}
          />

          {NAV_LINKS.map(({ to, label }) => (
            <Link
              key={to}
              to={to}
              ref={el => linkRefs.current[to] = el}
              className="nav-link"
              style={{
                color: location.pathname === to ? 'white' : '#b8ccb6',
                transition: 'color 0.2s ease',
                padding: '0.05rem 1rem',
                position: 'relative',
                zIndex: 1,
              }}
            >
              {label}
            </Link>
          ))}
        </div>
      </nav>

      {location.pathname !== '/about/' && (
        <div className="disclaimer-bar">
          ⚠️ This site is for informational purposes only and is not financial advice. Always do your own research.{' '}
          <Link to="/about/" className="disclaimer-link">Learn more</Link>
        </div>
      )}
      </header>

      <main className="p-4">
        <Outlet />
      </main>

      <footer className="site-footer">
        © 2026 Jacob Hennemann · SwingTrade is for informational purposes only and does not constitute financial advice.
      </footer>
    </div>
  )
}