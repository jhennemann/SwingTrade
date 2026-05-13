import { useState, useEffect } from 'react'
import { FaBookmark, FaRegBookmark } from 'react-icons/fa'

export default function WatchlistButton({ ticker, onRemove }) {
  const [bookmarked, setBookmarked] = useState(false)

  useEffect(() => {
    const watchlist = JSON.parse(localStorage.getItem('watchlist') ?? '[]')
    setBookmarked(watchlist.includes(ticker))
  }, [ticker])

  function toggle() {
    const watchlist = JSON.parse(localStorage.getItem('watchlist') ?? '[]')
    let updated
    if (bookmarked) {
      updated = watchlist.filter(t => t !== ticker)
      if (onRemove) onRemove()
    } else {
      updated = [...watchlist, ticker]
    }
    localStorage.setItem('watchlist', JSON.stringify(updated))
    setBookmarked(!bookmarked)
  }

  return (
    <button
      className="watchlist-btn"
      onClick={toggle}
      aria-label={bookmarked ? `Remove ${ticker} from watchlist` : `Add ${ticker} to watchlist`}
      aria-pressed={bookmarked}
    >
      {bookmarked ? <FaBookmark className="watchlist-icon-active" /> : <FaRegBookmark className="watchlist-icon" />}
    </button>
  )
}