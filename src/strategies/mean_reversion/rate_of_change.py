"""
Mean Reversion Strategy based on Rate of Change

Buys dips in uptrends and sells rallies in downtrends.
Uses short-term ROC to identify oversold/overbought conditions
within the context of the longer-term trend.
"""

from typing import Dict, Tuple
import pandas as pd
import numpy as np

from ..base_strategy import BaseStrategy


class MeanReversionLongStrategy(BaseStrategy):
    """
    Mean Reversion Long Strategy.
    
    Buys oversold dips when the market is in a longer-term uptrend.
    Requires price to be above the 200 MA (uptrend) and 
    short-term ROC to be below oversold threshold.
    """
    
    DEFAULT_PARAMS = {
        "trend_ma_period": 200,       # MA period for trend determination
        "roc_period": 5,              # Short-term ROC period
        "oversold_threshold": -0.05,  # ROC threshold for oversold (-5%)
        "exit_threshold": 0.0,        # ROC threshold to exit position
        "position_size": 1.0
    }
    
    def __init__(self, params: Dict = None):
        """
        Initialize Mean Reversion Long strategy.
        
        Args:
            params: Strategy parameters (uses defaults if not provided)
        """
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__("MeanReversion_Long", merged_params)
        self._in_position = False
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        if self.params["trend_ma_period"] < 1:
            raise ValueError("Trend MA period must be positive")
        if self.params["roc_period"] < 1:
            raise ValueError("ROC period must be positive")
        if self.params["oversold_threshold"] >= self.params["exit_threshold"]:
            raise ValueError("Oversold threshold must be less than exit threshold")
        if not 0 <= self.params["position_size"] <= 1:
            raise ValueError("Position size must be between 0 and 1")
    
    def generate_signal(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate trading signal.
        
        Args:
            data: DataFrame with OHLCV data for NDX
            
        Returns:
            Tuple of (tqqq_position, sqqq_position)
        """
        min_required = self.params["trend_ma_period"] + self.params["roc_period"]
        
        if len(data) < min_required:
            self._debug_info = {"status": "insufficient_data", "required": min_required, "available": len(data)}
            return (0.0, 0.0)
        
        # Calculate trend MA
        trend_ma = self.calculate_moving_average(data, self.params["trend_ma_period"])
        
        # Calculate short-term ROC
        roc = self.calculate_rate_of_change(data, self.params["roc_period"])
        
        current_close = data["close"].iloc[-1]
        current_ma = trend_ma.iloc[-1]
        current_roc = roc.iloc[-1]
        
        # Check if in uptrend
        in_uptrend = current_close > current_ma
        
        # Entry/exit logic
        oversold = current_roc < self.params["oversold_threshold"]
        recovered = current_roc > self.params["exit_threshold"]
        
        # State machine for position
        if not self._in_position and in_uptrend and oversold:
            self._in_position = True
        elif self._in_position and (recovered or not in_uptrend):
            self._in_position = False
        
        self._debug_info = {
            "current_price": current_close,
            "trend_ma": current_ma,
            "in_uptrend": in_uptrend,
            "current_roc": current_roc,
            "oversold": oversold,
            "in_position": self._in_position,
            "signal": "LONG" if self._in_position else "FLAT"
        }
        
        position_size = self.params["position_size"]
        
        if self._in_position:
            return (position_size, 0.0)
        else:
            return (0.0, 0.0)


class MeanReversionShortStrategy(BaseStrategy):
    """
    Mean Reversion Short Strategy.
    
    Shorts overbought rallies when the market is in a longer-term downtrend.
    Requires price to be below the 200 MA (downtrend) and 
    short-term ROC to be above overbought threshold.
    """
    
    DEFAULT_PARAMS = {
        "trend_ma_period": 200,
        "roc_period": 5,
        "overbought_threshold": 0.05,  # ROC threshold for overbought (+5%)
        "exit_threshold": 0.0,
        "position_size": 1.0
    }
    
    def __init__(self, params: Dict = None):
        """
        Initialize Mean Reversion Short strategy.
        
        Args:
            params: Strategy parameters (uses defaults if not provided)
        """
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__("MeanReversion_Short", merged_params)
        self._in_position = False
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        if self.params["trend_ma_period"] < 1:
            raise ValueError("Trend MA period must be positive")
        if self.params["roc_period"] < 1:
            raise ValueError("ROC period must be positive")
        if self.params["overbought_threshold"] <= self.params["exit_threshold"]:
            raise ValueError("Overbought threshold must be greater than exit threshold")
        if not 0 <= self.params["position_size"] <= 1:
            raise ValueError("Position size must be between 0 and 1")
    
    def generate_signal(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate trading signal.
        
        Args:
            data: DataFrame with OHLCV data for NDX
            
        Returns:
            Tuple of (tqqq_position, sqqq_position)
        """
        min_required = self.params["trend_ma_period"] + self.params["roc_period"]
        
        if len(data) < min_required:
            self._debug_info = {"status": "insufficient_data", "required": min_required, "available": len(data)}
            return (0.0, 0.0)
        
        # Calculate trend MA
        trend_ma = self.calculate_moving_average(data, self.params["trend_ma_period"])
        
        # Calculate short-term ROC
        roc = self.calculate_rate_of_change(data, self.params["roc_period"])
        
        current_close = data["close"].iloc[-1]
        current_ma = trend_ma.iloc[-1]
        current_roc = roc.iloc[-1]
        
        # Check if in downtrend
        in_downtrend = current_close < current_ma
        
        # Entry/exit logic
        overbought = current_roc > self.params["overbought_threshold"]
        recovered = current_roc < self.params["exit_threshold"]
        
        # State machine for position
        if not self._in_position and in_downtrend and overbought:
            self._in_position = True
        elif self._in_position and (recovered or not in_downtrend):
            self._in_position = False
        
        self._debug_info = {
            "current_price": current_close,
            "trend_ma": current_ma,
            "in_downtrend": in_downtrend,
            "current_roc": current_roc,
            "overbought": overbought,
            "in_position": self._in_position,
            "signal": "SHORT" if self._in_position else "FLAT"
        }
        
        position_size = self.params["position_size"]
        
        if self._in_position:
            return (0.0, position_size)
        else:
            return (0.0, 0.0)
