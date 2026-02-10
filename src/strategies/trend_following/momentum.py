"""
Momentum Strategy

Captures trends by measuring rate of change over a lookback period.
Long when momentum is positive and above threshold, short when negative.
"""

from typing import Dict, Tuple
import pandas as pd
import numpy as np

from ..base_strategy import BaseStrategy


class MomentumLongStrategy(BaseStrategy):
    """
    Momentum Long Strategy.
    
    Goes long TQQQ when momentum (rate of change) is positive
    over the lookback period.
    """
    
    DEFAULT_PARAMS = {
        "lookback_period": 126,      # ~6 months of trading days
        "threshold": 0.0,            # Minimum ROC to trigger long
        "smoothing_period": 5,       # Days to smooth momentum signal
        "position_size": 1.0
    }
    
    def __init__(self, params: Dict = None):
        """
        Initialize Momentum Long strategy.
        
        Args:
            params: Strategy parameters (uses defaults if not provided)
        """
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__("Momentum_Long", merged_params)
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        if self.params["lookback_period"] < 1:
            raise ValueError("Lookback period must be positive")
        if self.params["smoothing_period"] < 1:
            raise ValueError("Smoothing period must be positive")
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
        min_required = self.params["lookback_period"] + self.params["smoothing_period"]
        
        if len(data) < min_required:
            self._debug_info = {"status": "insufficient_data", "required": min_required, "available": len(data)}
            return (0.0, 0.0)
        
        # Calculate rate of change
        roc = self.calculate_rate_of_change(data, self.params["lookback_period"])
        
        # Smooth the momentum signal
        smoothed_roc = roc.rolling(window=self.params["smoothing_period"]).mean()
        
        current_momentum = smoothed_roc.iloc[-1]
        threshold = self.params["threshold"]
        
        self._debug_info = {
            "current_momentum": current_momentum,
            "threshold": threshold,
            "raw_roc": roc.iloc[-1],
            "signal": "LONG" if current_momentum > threshold else "FLAT"
        }
        
        # Generate position
        position_size = self.params["position_size"]
        
        if current_momentum > threshold:
            return (position_size, 0.0)
        else:
            return (0.0, 0.0)


class MomentumShortStrategy(BaseStrategy):
    """
    Momentum Short Strategy.
    
    Goes long SQQQ (short NASDAQ) when momentum is negative
    below the threshold.
    """
    
    DEFAULT_PARAMS = {
        "lookback_period": 126,
        "threshold": 0.0,            # Maximum ROC to trigger short
        "smoothing_period": 5,
        "position_size": 1.0
    }
    
    def __init__(self, params: Dict = None):
        """
        Initialize Momentum Short strategy.
        
        Args:
            params: Strategy parameters (uses defaults if not provided)
        """
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__("Momentum_Short", merged_params)
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        if self.params["lookback_period"] < 1:
            raise ValueError("Lookback period must be positive")
        if self.params["smoothing_period"] < 1:
            raise ValueError("Smoothing period must be positive")
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
        min_required = self.params["lookback_period"] + self.params["smoothing_period"]
        
        if len(data) < min_required:
            self._debug_info = {"status": "insufficient_data", "required": min_required, "available": len(data)}
            return (0.0, 0.0)
        
        # Calculate rate of change
        roc = self.calculate_rate_of_change(data, self.params["lookback_period"])
        
        # Smooth the momentum signal
        smoothed_roc = roc.rolling(window=self.params["smoothing_period"]).mean()
        
        current_momentum = smoothed_roc.iloc[-1]
        threshold = self.params["threshold"]
        
        self._debug_info = {
            "current_momentum": current_momentum,
            "threshold": threshold,
            "raw_roc": roc.iloc[-1],
            "signal": "SHORT" if current_momentum < threshold else "FLAT"
        }
        
        # Generate position
        position_size = self.params["position_size"]
        
        if current_momentum < threshold:
            return (0.0, position_size)
        else:
            return (0.0, 0.0)
