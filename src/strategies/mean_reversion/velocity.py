"""
Velocity Filter Strategy

Scales position sizes based on trend velocity (rate of price change).
When trend is accelerating, increase position size.
When trend is decelerating, reduce position size.
"""

from typing import Dict, Tuple
import pandas as pd
import numpy as np

from ..base_strategy import BaseStrategy


class VelocityFilterStrategy(BaseStrategy):
    """
    Velocity Filter Strategy.
    
    Acts as a position sizing overlay based on trend velocity.
    Returns a scaling factor (0 to 1) that can be used to adjust
    other strategy positions.
    
    Velocity is measured as the difference between fast and slow
    rate of change measurements.
    """
    
    DEFAULT_PARAMS = {
        "fast_period": 10,       # Fast ROC period
        "slow_period": 50,       # Slow ROC period
        "acceleration_threshold": 0.01,  # Min acceleration for full position
        "smoothing_period": 5,   # Days to smooth velocity
        "position_size": 1.0
    }
    
    def __init__(self, params: Dict = None):
        """
        Initialize Velocity Filter strategy.
        
        Args:
            params: Strategy parameters (uses defaults if not provided)
        """
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__("VelocityFilter", merged_params)
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        if self.params["fast_period"] >= self.params["slow_period"]:
            raise ValueError("Fast period must be less than slow period")
        if self.params["fast_period"] < 1:
            raise ValueError("Periods must be positive")
        if not 0 <= self.params["position_size"] <= 1:
            raise ValueError("Position size must be between 0 and 1")
    
    def generate_signal(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate trading signal based on velocity.
        
        Args:
            data: DataFrame with OHLCV data for NDX
            
        Returns:
            Tuple of (tqqq_position, sqqq_position)
            
        Note: This strategy is designed as a filter/overlay.
        It returns long signal when velocity is positive (accelerating upward)
        and short signal when velocity is negative (accelerating downward).
        """
        min_required = self.params["slow_period"] + self.params["smoothing_period"]
        
        if len(data) < min_required:
            self._debug_info = {"status": "insufficient_data", "required": min_required, "available": len(data)}
            return (0.0, 0.0)
        
        # Calculate fast and slow ROC
        fast_roc = self.calculate_rate_of_change(data, self.params["fast_period"])
        slow_roc = self.calculate_rate_of_change(data, self.params["slow_period"])
        
        # Velocity is the difference (acceleration/deceleration of trend)
        velocity = fast_roc - slow_roc
        
        # Smooth the velocity
        smoothed_velocity = velocity.rolling(window=self.params["smoothing_period"]).mean()
        
        current_velocity = smoothed_velocity.iloc[-1]
        threshold = self.params["acceleration_threshold"]
        
        # Determine direction and scaling
        if current_velocity > threshold:
            # Accelerating upward - go long
            scale = min(1.0, current_velocity / threshold)
            signal = "LONG"
            tqqq_pos = self.params["position_size"] * scale
            sqqq_pos = 0.0
        elif current_velocity < -threshold:
            # Accelerating downward - go short
            scale = min(1.0, abs(current_velocity) / threshold)
            signal = "SHORT"
            tqqq_pos = 0.0
            sqqq_pos = self.params["position_size"] * scale
        else:
            # No clear acceleration - stay flat
            scale = 0.0
            signal = "FLAT"
            tqqq_pos = 0.0
            sqqq_pos = 0.0
        
        self._debug_info = {
            "fast_roc": fast_roc.iloc[-1],
            "slow_roc": slow_roc.iloc[-1],
            "velocity": current_velocity,
            "threshold": threshold,
            "scale": scale,
            "signal": signal
        }
        
        return (tqqq_pos, sqqq_pos)
    
    def get_scaling_factor(self, data: pd.DataFrame) -> float:
        """
        Get the velocity-based scaling factor for position sizing.
        
        This can be used by other strategies to scale their positions.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            Scaling factor between 0 and 1
        """
        min_required = self.params["slow_period"] + self.params["smoothing_period"]
        
        if len(data) < min_required:
            return 0.5  # Default to half position if insufficient data
        
        # Calculate velocity
        fast_roc = self.calculate_rate_of_change(data, self.params["fast_period"])
        slow_roc = self.calculate_rate_of_change(data, self.params["slow_period"])
        velocity = fast_roc - slow_roc
        smoothed_velocity = velocity.rolling(window=self.params["smoothing_period"]).mean()
        
        current_velocity = abs(smoothed_velocity.iloc[-1])
        threshold = self.params["acceleration_threshold"]
        
        # Scale between 0.5 and 1.0 based on velocity
        if current_velocity < threshold:
            return 0.5
        else:
            return min(1.0, 0.5 + (current_velocity / threshold) * 0.5)
