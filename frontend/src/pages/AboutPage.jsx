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
              I'm Jacob Hennemann, a May 2026 graduate of the University of Wisconsin–Madison
              with a double major in Data Science and Computer Science.
              I've always been interested in the stock market, and SwingTrade started as a way to combine
              that with my technical skills — building something automated that actually does something
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

        {/* About the Project */}
        <div className="col-12">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaChartLine className="about-icon" /> About the Project
            </h5>
            <p className="about-text">
              SwingTrade is a fully automated swing trading system that scans the S&P 500 and NASDAQ 100
              every weekday after market close. It identifies stocks showing momentum near 52-week highs
              and paper trades them across two independent accounts with different exit configurations.
            </p>
            <p className="about-text">
              The backend runs automatically via GitHub Actions, stores results in a PostgreSQL database,
              and sends Discord alerts for active positions. This dashboard displays live paper trading
              results, signal history, and performance analytics in real time.
            </p>
          </div>
        </div>

        {/* 52-Week High Momentum Strategy - full width */}
        <div className="col-12">
          <div className="about-card">
            <h5 className="about-section-title">
              <FaFlask className="about-icon" /> 52-Week High Momentum Strategy
            </h5>
            <p className="about-text">
              The strategy targets stocks breaking out to new 52-week highs on above-average volume.
              The core thesis: stocks making new highs tend to continue higher, especially when the
              broader market is in an uptrend and the stock is outperforming the S&P 500.
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

            {/* RS Filter Discovery */}
            <div className="mt-4">
              <p className="about-text mb-2" style={{ fontWeight: 600, color: '#2c3a2c' }}>The RS Filter Discovery</p>
              <p className="about-text">
                After backtesting 6 years of signals (2020–2025) across the full S&P 500 + NASDAQ 100
                universe, a key finding emerged: filtering signals by relative strength dramatically
                improves performance. Without any filter, the strategy produces a 23% win rate across
                thousands of trades. But by requiring a relative strength score above 50 — meaning the
                stock has meaningfully outperformed SPY over the past 60 days — the signal quality
                improves significantly.
              </p>

              {/* RS table */}
              <div style={{ overflowX: 'auto', marginTop: '12px', marginBottom: '12px' }}>
                <table className="w-100 signals-table">
                  <thead>
                    <tr>
                      <th>RS Filter</th>
                      <th>Trades</th>
                      <th>Win Rate</th>
                      <th>Avg P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="text-secondary">None (all signals)</td>
                      <td className="text-secondary">4,631</td>
                      <td className="text-secondary">23.0%</td>
                      <td className="text-secondary">+0.60%</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">RS ≥ 25</td>
                      <td className="text-secondary">770</td>
                      <td className="text-secondary">22.3%</td>
                      <td className="text-secondary">+1.45%</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">RS ≥ 40</td>
                      <td className="text-secondary">314</td>
                      <td className="text-secondary">24.5%</td>
                      <td className="text-secondary">+2.07%</td>
                    </tr>
                    <tr>
                      <td style={{ color: '#4a7c59', fontWeight: 600 }}>RS ≥ 50 ✓ active filter</td>
                      <td style={{ color: '#4a7c59', fontWeight: 600 }}>197</td>
                      <td style={{ color: '#4a7c59', fontWeight: 600 }}>26.9%</td>
                      <td style={{ color: '#4a7c59', fontWeight: 600 }}>+2.51%</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">RS ≥ 60</td>
                      <td className="text-secondary">128</td>
                      <td className="text-secondary">25.8%</td>
                      <td className="text-secondary">+2.38%</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">RS ≥ 75</td>
                      <td className="text-secondary">75</td>
                      <td className="text-secondary">22.7%</td>
                      <td className="text-secondary">+1.85%</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <p className="about-text" style={{ fontSize: '0.85rem', color: '#5a6b58' }}>
                RS ≥ 50 was selected as the active filter — it maximizes both win rate and avg P&L
                while maintaining a statistically meaningful sample size of 197 trades across 2020–2025.
              </p>
            </div>

            {/* Year by year */}
            <div className="mt-4">
              <p className="about-text mb-2" style={{ fontWeight: 600, color: '#2c3a2c' }}>Backtest results by year (RS ≥ 50)</p>
              <div style={{ overflowX: 'auto' }}>
                <table className="w-100 signals-table">
                  <thead>
                    <tr>
                      <th>Year</th>
                      <th>Trades</th>
                      <th>Win Rate</th>
                      <th>Avg P&L</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="text-secondary">2021</td>
                      <td className="text-secondary">51</td>
                      <td className="rs-cell">25.5%</td>
                      <td className="rs-cell">+2.33%</td>
                      <td className="text-secondary" style={{ fontSize: '0.8rem' }}>Strong bull market</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">2022</td>
                      <td className="text-secondary">2</td>
                      <td className="loss-cell">0.0%</td>
                      <td className="loss-cell">-2.00%</td>
                      <td className="text-secondary" style={{ fontSize: '0.8rem' }}>Bear market, too few trades</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">2023</td>
                      <td className="text-secondary">24</td>
                      <td className="loss-cell">12.5%</td>
                      <td className="text-secondary">+0.12%</td>
                      <td className="text-secondary" style={{ fontSize: '0.8rem' }}>Choppy conditions</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">2024</td>
                      <td className="text-secondary">67</td>
                      <td className="rs-cell">35.8%</td>
                      <td className="rs-cell">+4.05%</td>
                      <td className="text-secondary" style={{ fontSize: '0.8rem' }}>Best year</td>
                    </tr>
                    <tr>
                      <td className="text-secondary">2025</td>
                      <td className="text-secondary">53</td>
                      <td className="rs-cell">24.5%</td>
                      <td className="rs-cell">+1.97%</td>
                      <td className="text-secondary" style={{ fontSize: '0.8rem' }}>Live paper trading began</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="about-text mt-3" style={{ fontSize: '0.85rem', color: '#5a6b58' }}>
                The strategy performs best in trending bull markets (2021, 2024) and struggles in
                choppy or bearish conditions (2022, 2023) — expected behavior for a momentum strategy.
                Live results are tracked on the{' '}
                <a href="#/paper/" className="about-link" style={{ fontSize: '0.85rem' }}>Paper Trading page</a>.
              </p>
            </div>
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
              <p className="about-text">Python, GitHub Actions</p>
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
              Every weekday after market close, SwingTrade automatically posts paper trading
              updates directly to Discord — closed trades, new entries, and open positions.
              Join to follow along in real time.
            </p>

            <div className="discord-preview">
              <div className="discord-header">
                <div className="discord-avatar">A</div>
                <div>
                  <span className="discord-bot-name">Alert Bot</span>
                  <span className="discord-badge">APP</span>
                  <span className="discord-timestamp">6/4/2026 5:58 PM</span>
                </div>
              </div>
              <div className="discord-message">
                <p className="discord-title">📊 Paper Trading Update — 2026-06-04</p>
                <p style={{ fontSize: '0.78rem', color: '#8a9a8a', marginBottom: '6px' }}>
                  52-Week High Momentum · 2 accounts · $1,000 each
                </p>
                <p className="discord-alert loss">🛑 <strong>Closed Today</strong><br />
                  MRVL [CON] — STOP | Entry: $318.05 → $311.69 | P&L: -2.00%<br />
                  HPE [CON] — STOP | Entry: $54.18 → $53.10 | P&L: -2.00%<br />
                  DELL [AGG] — STOP | Entry: $426.15 → $417.63 | P&L: -2.00%
                </p>
                <p className="discord-alert profit">📈 <strong>Entering Tomorrow at Open</strong><br />
                  MRVL [CON] | RS: 237.9 | Size: $561.00
                </p>
                <p className="discord-alert" style={{ background: '#1a2a1a', borderLeft: '3px solid #4a7c59' }}>
                  📂 <strong>Open Positions</strong><br />
                  MRVL [AGG] | RS: 211.9 | Entry: $282.95 | Stop: $277.29 | Target: $325.39 | Day 0/20
                </p>
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