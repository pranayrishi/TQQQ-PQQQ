"""
Strategy Aggregator

Combines signals from all individual strategies into
final position recommendations using weighted averaging.
"""

import logging
from typing import Dict, List, Tuple, Optional
import pandas as pd

from .base_strategy import BaseStrategy
from .trend_following.ma_breakout import MABreakoutLongStrategy, MABreakoutShortStrategy
from .trend_following.momentum import MomentumLongStrategy, MomentumShortStrategy
from .mean_reversion.rate_of_change import MeanReversionLongStrategy, MeanReversionShortStrategy
from .mean_reversion.velocity import VelocityFilterStrategy

logger = logging.getLogger(__name__)


class StrategyAggregator:
    """
    Aggregates multiple strategy signals into final positions.
    
    Default weights based on specification:
    - MA Breakout Long: 25%
    - MA Breakout Short: 15%
    - Momentum Long: 20%
    - Momentum Short: 10%
    - Mean Reversion Long: 10%
    - Mean Reversion Short: 10%
    - Velocity Filter: 10%
    """
    
    DEFAULT_WEIGHTS = {
        "MA_Breakout_Long": 0.25,
        "MA_Breakout_Short": 0.15,
        "Momentum_Long": 0.20,
        "Momentum_Short": 0.10,
        "MeanReversion_Long": 0.10,
        "MeanReversion_Short": 0.10,
        "VelocityFilter": 0.10
    }
    
    def __init__(self, config: Dict = None):
        """
        Initialize strategy aggregator.
        
        Args:
            config: Configuration dictionary with strategy parameters and weights
        """
        self.config = config or {}
        self.weights = self.config.get("weights", self.DEFAULT_WEIGHTS)
        
        # Initialize all strategies
        self.strategies: Dict[str, BaseStrategy] = {}
        self._init_strategies()
        
        # Store last signals for debugging
        self._last_signals: Dict[str, Tuple[float, float]] = {}
        self._last_aggregate: Tuple[float, float] = (0.0, 0.0)
    
    def _init_strategies(self) -> None:
        """Initialize all strategy instances."""
        strategy_params = self.config.get("strategy_params", {})
        
        # Trend Following - Long
        self.strategies["MA_Breakout_Long"] = MABreakoutLongStrategy(
            strategy_params.get("ma_breakout", {})
        )
        
        # Trend Following - Short
        self.strategies["MA_Breakout_Short"] = MABreakoutShortStrategy(
            strategy_params.get("ma_breakout", {})
        )
        
        # Momentum - Long
        self.strategies["Momentum_Long"] = MomentumLongStrategy(
            strategy_params.get("momentum", {})
        )
        
        # Momentum - Short
        self.strategies["Momentum_Short"] = MomentumShortStrategy(
            strategy_params.get("momentum", {})
        )
        
        # Mean Reversion - Long
        self.strategies["MeanReversion_Long"] = MeanReversionLongStrategy(
            strategy_params.get("mean_reversion", {})
        )
        
        # Mean Reversion - Short
        self.strategies["MeanReversion_Short"] = MeanReversionShortStrategy(
            strategy_params.get("mean_reversion", {})
        )
        
        # Velocity Filter
        self.strategies["VelocityFilter"] = VelocityFilterStrategy(
            strategy_params.get("velocity", {})
        )
        
        logger.info(f"Initialized {len(self.strategies)} strategies")
    
    def generate_signals(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate aggregated trading signals from all strategies.
        
        Args:
            data: DataFrame with OHLCV data for NDX
            
        Returns:
            Tuple of (tqqq_position, sqqq_position) as weighted averages
        """
        total_tqqq = 0.0
        total_sqqq = 0.0
        total_weight = 0.0
        
        self._last_signals = {}
        
        for name, strategy in self.strategies.items():
            weight = self.weights.get(name, 0.0)
            
            if weight <= 0:
                continue
            
            try:
                tqqq, sqqq = strategy.generate_signal(data)
                
                self._last_signals[name] = (tqqq, sqqq)
                
                total_tqqq += tqqq * weight
                total_sqqq += sqqq * weight
                total_weight += weight
                
                logger.debug(f"{name}: TQQQ={tqqq:.2%}, SQQQ={sqqq:.2%}, weight={weight:.2%}")
                
            except Exception as e:
                logger.error(f"Strategy {name} failed: {e}")
                continue
        
        # Normalize by total weight
        if total_weight > 0:
            final_tqqq = total_tqqq / total_weight
            final_sqqq = total_sqqq / total_weight
        else:
            final_tqqq = 0.0
            final_sqqq = 0.0
        
        # Ensure positions are mutually exclusive for trend following
        # If both are non-zero, take the larger one
        if final_tqqq > 0 and final_sqqq > 0:
            if final_tqqq >= final_sqqq:
                final_sqqq = 0.0
            else:
                final_tqqq = 0.0
        
        # Clamp to valid range
        final_tqqq = max(0.0, min(1.0, final_tqqq))
        final_sqqq = max(0.0, min(1.0, final_sqqq))
        
        self._last_aggregate = (final_tqqq, final_sqqq)
        
        logger.info(f"Aggregated signal: TQQQ={final_tqqq:.2%}, SQQQ={final_sqqq:.2%}")
        
        return (final_tqqq, final_sqqq)
    
    def get_individual_signals(self) -> Dict[str, Tuple[float, float]]:
        """
        Get the last generated signals from each strategy.
        
        Returns:
            Dictionary mapping strategy name to (tqqq, sqqq) tuple
        """
        return self._last_signals.copy()
    
    def get_debug_info(self) -> Dict:
        """
        Get comprehensive debug information.
        
        Returns:
            Dictionary with all strategy debug info
        """
        debug = {
            "aggregate": {
                "tqqq": self._last_aggregate[0],
                "sqqq": self._last_aggregate[1]
            },
            "weights": self.weights.copy(),
            "strategies": {}
        }
        
        for name, strategy in self.strategies.items():
            debug["strategies"][name] = {
                "signal": self._last_signals.get(name, (0.0, 0.0)),
                "debug": strategy.get_debug_info()
            }
        
        return debug
    
    def set_weights(self, weights: Dict[str, float]) -> None:
        """
        Update strategy weights.
        
        Args:
            weights: Dictionary mapping strategy name to weight
        """
        # Validate weights
        for name in weights:
            if name not in self.strategies:
                raise ValueError(f"Unknown strategy: {name}")
        
        self.weights.update(weights)
        logger.info(f"Updated weights: {self.weights}")
    
    def get_strategy_names(self) -> List[str]:
        """Get list of all strategy names."""
        return list(self.strategies.keys())
    
    def reset_state(self) -> None:
        """Reset any stateful strategies (e.g., mean reversion)."""
        for name, strategy in self.strategies.items():
            if hasattr(strategy, '_in_position'):
                strategy._in_position = False
        
        self._last_signals = {}
        self._last_aggregate = (0.0, 0.0)
        
        logger.info("Strategy states reset")
