import '../App.css'
import { FaUser, FaChartLine, FaChartBar, FaCode, FaLinkedin, FaGithub, FaPython, FaReact, FaDatabase, FaDiscord, FaFlask } from 'react-icons/fa'
import { useEffect } from 'react'

export default function AboutPage() {
  useEffect(() => {
    document.title = 'SwingTrade | About'
  }, [])

  return (
    <div className="about-container">
      <h1 className="mb-4">About</h1>

      <div className="row g-4">

        {/* About Me - full width */}
        <div className="col-12">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaUser className="about-icon" /> About Me
            </h5>
            <p className="about-text">
              I'm Jacob Hennemann, a Senior at the University of Wisconsin–Madison
              graduating in May 2026, double majoring in Data Science and Computer Science.
              I've always been into the stock market, and SwingTrade started as a way to combine
              that with my technical skills, building something automated that actually does something
              useful. The frontend dashboard was later added as part of a CS 571 course project, turning
              it into a full-stack application.
            </p>
            <div className="about-links">
              <a href="https://www.linkedin.com/in/jacob-hennemann" target="_blank" rel="noreferrer" className="about-link">
                <FaLinkedin className="link-icon" /> LinkedIn
              </a>
              <a href="https://github.com/jhennemann/SwingTrade" target="_blank" rel="noreferrer" className="about-link">
                <FaGithub className="link-icon" /> GitHub
              </a>
            </div>
          </div>
        </div>

        {/* About the Project + Pullback Strategy */}
        <div className="col-md-6">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaChartLine className="about-icon" /> About the Project
            </h5>
            <p className="about-text">
              SwingTrade is a fully automated swing trading system that scans the S&P 500 and NASDAQ 100
              every weekday after market close. It looks for stocks showing specific short-term trading
              patterns and surfaces them as signals for review.
            </p>
            <p className="about-text">
              The backend runs automatically via GitHub Actions, stores results in a PostgreSQL database,
              and sends Discord alerts for active positions. This dashboard displays the scan results
              in an interactive, filterable interface.
            </p>
          </div>
        </div>

        <div className="col-md-6">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaChartBar className="about-icon" /> Pullback Uptrend Strategy
            </h5>
            <p className="about-text">
              The primary strategy looks for stocks in a strong uptrend that have temporarily pulled
              back to their 20-day moving average and are showing signs of recovery.
            </p>
            <ul className="about-list">
              <li>Stock must be above its 50-day moving average</li>
              <li>Price pulls back to within 2% of the SMA20</li>
              <li>Recovery candle with above average volume</li>
              <li>Stop loss set at 2% below entry</li>
              <li>Profit target set at 7% above entry</li>
              <li>10 day maximum hold time</li>
              <li>Market filter: only active when SPY is above SMA200</li>
            </ul>
          </div>
        </div>

        {/* Paper Trading - full width */}
        <div className="col-12">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaFlask className="about-icon" /> Paper Trading — 52-Week High Momentum
            </h5>
            <p className="about-text">
              A second strategy is being actively paper traded in real time alongside the market.
              Rather than backtesting only, two independent $1,000 accounts run simultaneously with
              different exit configurations, so performance can be compared live as signals come in.
            </p>

            <div className="row g-3 mt-1">
              <div className="col-md-6">
                <p className="about-text mb-1" style={{ fontWeight: 600, color: '#2c3a2c' }}>Signal conditions</p>
                <ul className="about-list">
                  <li>Stock closes within 2% of its 52-week high</li>
                  <li>Volume at least 1.75x the 20-day average</li>
                  <li>Above both the SMA50 and SMA200</li>
                  <li>Relative strength vs SPY (60d) above 50</li>
                  <li>Market filter: SPY above SMA200</li>
                </ul>
              </div>
              <div className="col-md-6">
                <p className="about-text mb-1" style={{ fontWeight: 600, color: '#2c3a2c' }}>Two accounts, same signals</p>
                <ul className="about-list">
                  <li>Each account starts at $1,000, max 2 positions</li>
                  <li>Position size adjusts dynamically with equity</li>
                  <li>Top RS signals fill open slots each evening</li>
                  <li><span style={{ color: '#4a7c59', fontWeight: 600 }}>Conservative:</span> 7% target, 10 day max hold</li>
                  <li><span style={{ color: '#c8a84b', fontWeight: 600 }}>Aggressive:</span> 15% target, 20 day max hold</li>
                  <li>Both use a 2% stop loss</li>
                </ul>
              </div>
            </div>

            <p className="about-text mt-3" style={{ fontSize: '0.85rem', color: '#5a6b58' }}>
              Backtest results across 246 trades (2021–2025): ~30% win rate overall, rising to 77.8% when
              filtered to RS &gt; 50. Live results are tracked on the{' '}
              <a href="#/paper/" className="about-link" style={{ fontSize: '0.85rem' }}>Paper Trading page</a>.
            </p>
          </div>
        </div>

        {/* Tech Stack + Discord */}
        <div className="col-md-6">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaCode className="about-icon" /> Tech Stack
            </h5>
            <div className="tech-group">
              <span className="tech-label"><FaPython className="tech-icon" /> Backend</span>
              <p className="about-text">Python, GitHub Actions, Google Sheets</p>
            </div>
            <div className="tech-group">
              <span className="tech-label"><FaReact className="tech-icon" /> Frontend</span>
              <p className="about-text">React, Vite, Bootstrap</p>
            </div>
            <div className="tech-group">
              <span className="tech-label"><FaDatabase className="tech-icon" /> Database</span>
              <p className="about-text">Supabase (PostgreSQL)</p>
            </div>
            <div className="tech-group">
              <span className="tech-label"><FaDiscord className="tech-icon" /> Alerts</span>
              <p className="about-text">Discord</p>
            </div>
          </div>
        </div>

        <div className="col-md-6">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaDiscord className="about-icon" /> Discord Community
            </h5>
            <p className="about-text">
              Every weekday after market close, SwingTrade automatically posts scan results
              and position alerts directly to Discord. Join to follow along in real time.
            </p>

            <div className="discord-preview">
              <div className="discord-header">
                <div className="discord-avatar">A</div>
                <div>
                  <span className="discord-bot-name">Alert Bot</span>
                  <span className="discord-badge">APP</span>
                  <span className="discord-timestamp">Today at 6:11 PM</span>
                </div>
              </div>
              <div className="discord-message">
                <p className="discord-title">🚨 SwingTrade Alerts</p>
                <p className="discord-alert profit">✅ <strong>MRNA HIT PROFIT TARGET</strong><br />
                  Entry: $46.93 | Current: $51.13 (+9.0%)<br />
                  Target: $50.22 | Day 6/10</p>
                <p className="discord-alert profit">✅ <strong>FCX HIT PROFIT TARGET</strong><br />
                  Entry: $61.40 | Current: $68.81 (+12.1%)<br />
                  Target: $65.70 | Day 6/10</p>
                <p className="discord-alert loss">🛑 <strong>ADM HIT STOP LOSS</strong><br />
                  Entry: $69.08 | Current: $67.70 (-2.0%)<br />
                  Stop: $67.70 | Day 5/10</p>
              </div>
            </div>

            <div className="about-links mt-3">
              <a href="YOUR_DISCORD_INVITE_LINK" target="_blank" rel="noreferrer" className="about-link discord-link">
                <FaDiscord className="link-icon" /> Join the Discord
              </a>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}