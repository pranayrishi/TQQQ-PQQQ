"""
Market Calendar

Determines trading days, market hours, and holidays.
"""

from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple, List
import pandas as pd

try:
    import exchange_calendars as xcals
    HAS_EXCHANGE_CALENDARS = True
except ImportError:
    HAS_EXCHANGE_CALENDARS = False


class MarketCalendar:
    """
    Market calendar for US equities.
    
    Uses exchange_calendars library for accurate
    holiday and trading hour information.
    Falls back to simple weekday check if library not available.
    """
    
    # US market holidays (approximate, for fallback)
    US_HOLIDAYS_2024_2026 = [
        "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29",
        "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02",
        "2024-11-28", "2024-12-25",
        "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
        "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
        "2025-11-27", "2025-12-25",
        "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
        "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
        "2026-11-26", "2026-12-25",
    ]
    
    def __init__(self):
        """Initialize market calendar."""
        if HAS_EXCHANGE_CALENDARS:
            self.calendar = xcals.get_calendar("XNYS")  # NYSE calendar
        else:
            self.calendar = None
            self._holidays = set(self.US_HOLIDAYS_2024_2026)
    
    def is_trading_day(self, check_date: date) -> bool:
        """
        Check if a date is a trading day.
        
        Args:
            check_date: Date to check
            
        Returns:
            True if markets are open
        """
        if isinstance(check_date, datetime):
            check_date = check_date.date()
        
        if self.calendar:
            try:
                ts = pd.Timestamp(check_date)
                return self.calendar.is_session(ts)
            except Exception:
                pass
        
        # Fallback: weekday and not a holiday
        if check_date.weekday() >= 5:  # Saturday or Sunday
            return False
        
        date_str = check_date.strftime("%Y-%m-%d")
        return date_str not in self._holidays
    
    def get_next_trading_day(self, from_date: date) -> date:
        """Get the next trading day after a date."""
        if isinstance(from_date, datetime):
            from_date = from_date.date()
        
        if self.calendar:
            try:
                ts = pd.Timestamp(from_date)
                sessions = self.calendar.sessions_in_range(ts, ts + pd.Timedelta(days=10))
                
                for session in sessions:
                    if session.date() > from_date:
                        return session.date()
            except Exception:
                pass
        
        # Fallback
        next_day = from_date + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
            if (next_day - from_date).days > 10:
                break
        
        return next_day
    
    def get_previous_trading_day(self, from_date: date) -> date:
        """Get the previous trading day before a date."""
        if isinstance(from_date, datetime):
            from_date = from_date.date()
        
        prev_day = from_date - timedelta(days=1)
        while not self.is_trading_day(prev_day):
            prev_day -= timedelta(days=1)
            if (from_date - prev_day).days > 10:
                break
        
        return prev_day
    
    def get_market_hours(self, trading_date: date) -> Optional[Tuple[time, time]]:
        """
        Get market open/close times for a date.
        
        Returns:
            Tuple of (open_time, close_time) or None if not trading day
        """
        if not self.is_trading_day(trading_date):
            return None
        
        if self.calendar:
            try:
                ts = pd.Timestamp(trading_date)
                open_time = self.calendar.session_open(ts)
                close_time = self.calendar.session_close(ts)
                return (open_time.time(), close_time.time())
            except Exception:
                pass
        
        # Standard market hours
        return (time(9, 30), time(16, 0))
    
    def minutes_until_close(self, current_time: datetime) -> int:
        """Calculate minutes until market close."""
        market_hours = self.get_market_hours(current_time.date())
        
        if market_hours is None:
            return -1
        
        close_time = datetime.combine(current_time.date(), market_hours[1])
        
        # Handle timezone-aware datetimes
        if current_time.tzinfo is not None and close_time.tzinfo is None:
            close_time = close_time.replace(tzinfo=current_time.tzinfo)
        
        if current_time >= close_time:
            return 0
        
        delta = close_time - current_time
        return int(delta.total_seconds() / 60)
    
    def is_market_open(self, current_time: datetime) -> bool:
        """Check if market is currently open."""
        if not self.is_trading_day(current_time.date()):
            return False
        
        market_hours = self.get_market_hours(current_time.date())
        if market_hours is None:
            return False
        
        current_t = current_time.time()
        return market_hours[0] <= current_t <= market_hours[1]
    
    def get_trading_days_between(self, start_date: date, end_date: date) -> List[date]:
        """Get list of trading days between two dates."""
        if self.calendar:
            try:
                sessions = self.calendar.sessions_in_range(
                    pd.Timestamp(start_date),
                    pd.Timestamp(end_date)
                )
                return [s.date() for s in sessions]
            except Exception:
                pass
        
        # Fallback
        trading_days = []
        current = start_date
        while current <= end_date:
            if self.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)
        
        return trading_days
    
    def count_trading_days(self, start_date: date, end_date: date) -> int:
        """Count trading days between two dates."""
        return len(self.get_trading_days_between(start_date, end_date))
