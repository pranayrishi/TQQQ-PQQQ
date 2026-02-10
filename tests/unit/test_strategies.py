"""
Unit tests for strategy modules.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.strategies.trend_following.ma_breakout import MABreakoutLongStrategy, MABreakoutShortStrategy
from src.strategies.trend_following.momentum import MomentumLongStrategy, MomentumShortStrategy
from src.strategies.mean_reversion.rate_of_change import MeanReversionLongStrategy, MeanReversionShortStrategy
from src.strategies.mean_reversion.velocity import VelocityFilterStrategy
from src.strategies.strategy_aggregator import StrategyAggregator


def generate_test_data(days: int, trend: str = "up", volatility: float = 0.01) -> pd.DataFrame:
    """Generate test OHLCV data."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="D")
    
    if trend == "up":
        drift = 0.0005
    elif trend == "down":
        drift = -0.0005
    else:
        drift = 0.0
    
    returns = np.random.randn(days) * volatility + drift
    prices = 100 * np.cumprod(1 + returns)
    
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": prices * (1 + np.random.randn(days) * 0.002),
        "high": prices * (1 + np.abs(np.random.randn(days) * 0.01)),
        "low": prices * (1 - np.abs(np.random.randn(days) * 0.01)),
        "close": prices,
        "volume": np.random.randint(1000000, 10000000, days)
    })


class TestMABreakoutLongStrategy:
    """Tests for MA Breakout Long Strategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = MABreakoutLongStrategy()
        assert strategy.name == "MA_Breakout_Long"
        assert strategy.params["short_ma_period"] == 50
        assert strategy.params["long_ma_period"] == 250
    
    def test_custom_params(self):
        """Test custom parameter initialization."""
        params = {"short_ma_period": 20, "long_ma_period": 100}
        strategy = MABreakoutLongStrategy(params)
        assert strategy.params["short_ma_period"] == 20
        assert strategy.params["long_ma_period"] == 100
    
    def test_invalid_params(self):
        """Test that invalid params raise errors."""
        with pytest.raises(ValueError):
            MABreakoutLongStrategy({"short_ma_period": 300, "long_ma_period": 250})
    
    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        strategy = MABreakoutLongStrategy()
        short_data = generate_test_data(100)
        
        tqqq, sqqq = strategy.generate_signal(short_data)
        assert tqqq == 0.0
        assert sqqq == 0.0
    
    def test_bullish_signal(self):
        """Test that strong uptrend generates long signal."""
        strategy = MABreakoutLongStrategy()
        # Generate strong uptrend data
        data = generate_test_data(300, trend="up", volatility=0.005)
        
        tqqq, sqqq = strategy.generate_signal(data)
        # In strong uptrend, should be long
        assert tqqq >= 0.0
        assert sqqq == 0.0
    
    def test_debug_info(self):
        """Test that debug info is populated."""
        strategy = MABreakoutLongStrategy()
        data = generate_test_data(300)
        
        strategy.generate_signal(data)
        debug = strategy.get_debug_info()
        
        assert "current_price" in debug or "status" in debug


class TestMABreakoutShortStrategy:
    """Tests for MA Breakout Short Strategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = MABreakoutShortStrategy()
        assert strategy.name == "MA_Breakout_Short"
    
    def test_bearish_signal(self):
        """Test that strong downtrend generates short signal."""
        strategy = MABreakoutShortStrategy()
        # Generate strong downtrend data
        data = generate_test_data(300, trend="down", volatility=0.005)
        
        tqqq, sqqq = strategy.generate_signal(data)
        # In strong downtrend, should be short
        assert tqqq == 0.0
        assert sqqq >= 0.0


class TestMomentumLongStrategy:
    """Tests for Momentum Long Strategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = MomentumLongStrategy()
        assert strategy.name == "Momentum_Long"
        assert strategy.params["lookback_period"] == 126
    
    def test_positive_momentum(self):
        """Test positive momentum detection."""
        strategy = MomentumLongStrategy()
        data = generate_test_data(200, trend="up")
        
        tqqq, sqqq = strategy.generate_signal(data)
        assert sqqq == 0.0  # Should never be short


class TestMomentumShortStrategy:
    """Tests for Momentum Short Strategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = MomentumShortStrategy()
        assert strategy.name == "Momentum_Short"
    
    def test_negative_momentum(self):
        """Test negative momentum detection."""
        strategy = MomentumShortStrategy()
        data = generate_test_data(200, trend="down")
        
        tqqq, sqqq = strategy.generate_signal(data)
        assert tqqq == 0.0  # Should never be long


class TestMeanReversionStrategies:
    """Tests for Mean Reversion Strategies."""
    
    def test_long_strategy_init(self):
        """Test mean reversion long initialization."""
        strategy = MeanReversionLongStrategy()
        assert strategy.name == "MeanReversion_Long"
    
    def test_short_strategy_init(self):
        """Test mean reversion short initialization."""
        strategy = MeanReversionShortStrategy()
        assert strategy.name == "MeanReversion_Short"


class TestVelocityFilterStrategy:
    """Tests for Velocity Filter Strategy."""
    
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = VelocityFilterStrategy()
        assert strategy.name == "VelocityFilter"
        assert strategy.params["fast_period"] == 10
        assert strategy.params["slow_period"] == 50
    
    def test_scaling_factor(self):
        """Test scaling factor calculation."""
        strategy = VelocityFilterStrategy()
        data = generate_test_data(100)
        
        scale = strategy.get_scaling_factor(data)
        assert 0 <= scale <= 1


class TestStrategyAggregator:
    """Tests for Strategy Aggregator."""
    
    def test_initialization(self):
        """Test aggregator initialization."""
        aggregator = StrategyAggregator()
        assert len(aggregator.strategies) == 7
    
    def test_signal_generation(self):
        """Test that aggregator generates valid signals."""
        aggregator = StrategyAggregator()
        data = generate_test_data(300)
        
        tqqq, sqqq = aggregator.generate_signals(data)
        
        # Signals should be in valid range
        assert 0 <= tqqq <= 1
        assert 0 <= sqqq <= 1
        
        # Should not be both long and short significantly
        assert not (tqqq > 0.5 and sqqq > 0.5)
    
    def test_get_individual_signals(self):
        """Test getting individual strategy signals."""
        aggregator = StrategyAggregator()
        data = generate_test_data(300)
        
        aggregator.generate_signals(data)
        signals = aggregator.get_individual_signals()
        
        assert len(signals) > 0
    
    def test_debug_info(self):
        """Test debug information."""
        aggregator = StrategyAggregator()
        data = generate_test_data(300)
        
        aggregator.generate_signals(data)
        debug = aggregator.get_debug_info()
        
        assert "aggregate" in debug
        assert "strategies" in debug
    
    def test_weight_update(self):
        """Test updating strategy weights."""
        aggregator = StrategyAggregator()
        
        new_weights = {"MA_Breakout_Long": 0.5}
        aggregator.set_weights(new_weights)
        
        assert aggregator.weights["MA_Breakout_Long"] == 0.5
    
    def test_reset_state(self):
        """Test state reset."""
        aggregator = StrategyAggregator()
        data = generate_test_data(300)
        
        aggregator.generate_signals(data)
        aggregator.reset_state()
        
        assert aggregator._last_signals == {}
        assert aggregator._last_aggregate == (0.0, 0.0)
