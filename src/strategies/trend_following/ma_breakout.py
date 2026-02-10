"""
Moving Average Breakout Strategy

This is the PRIMARY strategy based on the core insight:
- Go long TQQQ when price is above BOTH the 50-day and 250-day moving averages
- Go short (SQQQ) when price is below BOTH the 50-day and 250-day moving averages
- Stay flat (cash) when price is between the MAs (mixed signals)

This strategy captures the bulk of profits according to the source.
"""

from typing import Dict, Tuple
import pandas as pd
import numpy as np

from ..base_strategy import BaseStrategy


class MABreakoutLongStrategy(BaseStrategy):
    """
    Moving Average Breakout Long Strategy.
    
    Goes long TQQQ when price is above both 50-day and 250-day MAs.
    Based on the principle that significant rallies cannot occur
    without price being above key moving averages.
    """
    
    DEFAULT_PARAMS = {
        "short_ma_period": 50,    # Short-term moving average
        "long_ma_period": 250,    # Long-term moving average
        "confirmation_days": 1,   # Days price must be above MAs
        "position_size": 1.0      # Full position when signal is active
    }
    
    def __init__(self, params: Dict = None):
        """
        Initialize MA Breakout Long strategy.
        
        Args:
            params: Strategy parameters (uses defaults if not provided)
        """
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__("MA_Breakout_Long", merged_params)
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        if self.params["short_ma_period"] >= self.params["long_ma_period"]:
            raise ValueError("Short MA period must be less than long MA period")
        if self.params["short_ma_period"] < 1:
            raise ValueError("MA periods must be positive")
        if not 0 <= self.params["position_size"] <= 1:
            raise ValueError("Position size must be between 0 and 1")
    
    def generate_signal(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate trading signal.
        
        Args:
            data: DataFrame with OHLCV data for NDX (NASDAQ-100 index)
            
        Returns:
            Tuple of (tqqq_position, sqqq_position)
        """
        min_required = self.params["long_ma_period"] + self.params["confirmation_days"]
        
        if len(data) < min_required:
            self._debug_info = {"status": "insufficient_data", "required": min_required, "available": len(data)}
            return (0.0, 0.0)
        
        # Calculate moving averages
        short_ma = self.calculate_moving_average(data, self.params["short_ma_period"])
        long_ma = self.calculate_moving_average(data, self.params["long_ma_period"])
        
        # Get recent values for confirmation
        confirm_days = self.params["confirmation_days"]
        recent_closes = data["close"].tail(confirm_days).values
        recent_short_ma = short_ma.tail(confirm_days).values
        recent_long_ma = long_ma.tail(confirm_days).values
        
        # Check if price is above both MAs for all confirmation days
        above_both = all(
            close > short_ma_val and close > long_ma_val
            for close, short_ma_val, long_ma_val 
            in zip(recent_closes, recent_short_ma, recent_long_ma)
        )
        
        # Store debug info
        current_close = data["close"].iloc[-1]
        current_short_ma = short_ma.iloc[-1]
        current_long_ma = long_ma.iloc[-1]
        
        self._debug_info = {
            "current_price": current_close,
            "short_ma": current_short_ma,
            "long_ma": current_long_ma,
            "above_short_ma": current_close > current_short_ma,
            "above_long_ma": current_close > current_long_ma,
            "signal": "LONG" if above_both else "FLAT"
        }
        
        # Generate position
        position_size = self.params["position_size"]
        
        if above_both:
            return (position_size, 0.0)
        else:
            return (0.0, 0.0)


class MABreakoutShortStrategy(BaseStrategy):
    """
    Moving Average Breakout Short Strategy.
    
    Goes long SQQQ (short NASDAQ) when price is below both 50-day and 250-day MAs.
    """
    
    DEFAULT_PARAMS = {
        "short_ma_period": 50,
        "long_ma_period": 250,
        "confirmation_days": 1,
        "position_size": 1.0
    }
    
    def __init__(self, params: Dict = None):
        """
        Initialize MA Breakout Short strategy.
        
        Args:
            params: Strategy parameters (uses defaults if not provided)
        """
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__("MA_Breakout_Short", merged_params)
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        if self.params["short_ma_period"] >= self.params["long_ma_period"]:
            raise ValueError("Short MA period must be less than long MA period")
        if self.params["short_ma_period"] < 1:
            raise ValueError("MA periods must be positive")
        if not 0 <= self.params["position_size"] <= 1:
            raise ValueError("Position size must be between 0 and 1")
    
    def generate_signal(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate trading signal.
        
        Args:
            data: DataFrame with OHLCV data for NDX (NASDAQ-100 index)
            
        Returns:
            Tuple of (tqqq_position, sqqq_position)
        """
        min_required = self.params["long_ma_period"] + self.params["confirmation_days"]
        
        if len(data) < min_required:
            self._debug_info = {"status": "insufficient_data", "required": min_required, "available": len(data)}
            return (0.0, 0.0)
        
        # Calculate moving averages
        short_ma = self.calculate_moving_average(data, self.params["short_ma_period"])
        long_ma = self.calculate_moving_average(data, self.params["long_ma_period"])
        
        # Get recent values for confirmation
        confirm_days = self.params["confirmation_days"]
        recent_closes = data["close"].tail(confirm_days).values
        recent_short_ma = short_ma.tail(confirm_days).values
        recent_long_ma = long_ma.tail(confirm_days).values
        
        # Check if price is below both MAs for all confirmation days
        below_both = all(
            close < short_ma_val and close < long_ma_val
            for close, short_ma_val, long_ma_val 
            in zip(recent_closes, recent_short_ma, recent_long_ma)
        )
        
        # Store debug info
        current_close = data["close"].iloc[-1]
        current_short_ma = short_ma.iloc[-1]
        current_long_ma = long_ma.iloc[-1]
        
        self._debug_info = {
            "current_price": current_close,
            "short_ma": current_short_ma,
            "long_ma": current_long_ma,
            "below_short_ma": current_close < current_short_ma,
            "below_long_ma": current_close < current_long_ma,
            "signal": "SHORT" if below_both else "FLAT"
        }
        
        # Generate position
        position_size = self.params["position_size"]
        
        if below_both:
            return (0.0, position_size)
        else:
            return (0.0, 0.0)
