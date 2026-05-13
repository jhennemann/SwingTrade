import { useEffect, useState } from 'react'
import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'
import { supabase } from '../supabase.js'
import '../App.css'
import SignalTable from '../components/SignalTable.jsx'

export default function SignalsPage() {
  const [validDates, setValidDates] = useState([])
  const [selectedDate, setSelectedDate] = useState(null)
  const [signalsByDate, setSignalsByDate] = useState({})
  const [sortBy, setSortBy] = useState('rank')
  const [viewMode, setViewMode] = useState('single')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchDates()
    document.title = 'SwingTrade | Signals'
  }, [])

  useEffect(() => {
    if (viewMode === 'single' && selectedDate) {
      fetchSignalsForDate(selectedDate)
    } else if (viewMode === 'last10' && validDates.length > 0) {
      fetchLast10()
    }
  }, [selectedDate, sortBy, viewMode, validDates])

  async function fetchDates() {
    const { data } = await supabase
      .from('signals')
      .select('last_date')
      .order('last_date', { ascending: false })

    const unique = [...new Set(data.map(r => r.last_date))]
    const dateObjects = unique.map(d => new Date(d + 'T12:00:00'))
    setValidDates(dateObjects)
    setSelectedDate(dateObjects[0])
  }

  async function fetchSignalsForDate(date) {
    setLoading(true)
    const dateStr = date.toISOString().split('T')[0]
    const { data } = await supabase
      .from('signals')
      .select('*')
      .eq('last_date', dateStr)
      .order(sortBy === 'rank' ? 'rank' : 'relative_strength', { ascending: sortBy === 'rank' })

    setSignalsByDate({ [dateStr]: data ?? [] })
    setLoading(false)
  }

  async function fetchLast10() {
    setLoading(true)
    const last10 = validDates.slice(0, 10)
    const dateStrs = last10.map(d => d.toISOString().split('T')[0])

    const result = {}
    for (const dateStr of dateStrs) {
      const { data } = await supabase
        .from('signals')
        .select('*')
        .eq('last_date', dateStr)
        .order(sortBy === 'rank' ? 'rank' : 'relative_strength', { ascending: sortBy === 'rank' })

      result[dateStr] = data ?? []
    }

    setSignalsByDate(result)
    setLoading(false)
  }

  function sortSignals(signals) {
    if (sortBy === 'pnl') {
      return [...signals].sort((a, b) => (b.win_loss ?? -999) - (a.win_loss ?? -999))
    }
    return signals
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1>Signals</h1>
        <div className="d-flex gap-3 align-items-center">
          {viewMode === 'single' && (
            <DatePicker
              selected={selectedDate}
              onChange={date => setSelectedDate(date)}
              includeDates={validDates}
              dateFormat="yyyy-MM-dd"
              className="signals-select"
              calendarClassName="signals-calendar"
            />
          )}
          <select
            className="signals-select"
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
          >
            <option value="rank">Sort by Rank</option>
            <option value="pnl">Sort by P&L</option>
          </select>
          <div className="view-toggle">
            <button
              className={`toggle-btn ${viewMode === 'single' ? 'active' : ''}`}
              onClick={() => setViewMode('single')}
            >
              Single Day
            </button>
            <button
              className={`toggle-btn ${viewMode === 'last10' ? 'active' : ''}`}
              onClick={() => setViewMode('last10')}
            >
              Last 10 Days
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <p className="text-secondary">Loading...</p>
      ) : (
        Object.entries(signalsByDate).map(([date, signals]) => (
          <div key={date} className="mb-5">
            <div className="signals-date-header">{date}</div>
            <SignalTable signals={signals} sortSignals={sortSignals} />
          </div>
        ))
      )}
    </div>
  )
}