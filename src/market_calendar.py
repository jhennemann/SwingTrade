import pandas_market_calendars as mcal
from datetime import date

def market_is_open(check_date: date | None = None) -> bool:
    """
    Returns True if NYSE is open on the given date.
    Defaults to today (UTC-safe).
    """
    nyse = mcal.get_calendar("NYSE")

    if check_date is None:
        check_date = date.today()

    schedule = nyse.schedule(
        start_date=check_date.isoformat(),
        end_date=check_date.isoformat()
    )

    return not schedule.empty
