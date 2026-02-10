"""
Integration tests for full backtest workflow.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
from datetime import datetime

from src.data.data_manager import DataManager
from src.data.cache_manager import CacheManager
from src.strategies.strategy_aggregator import StrategyAggregator
from src.backtest.backtest_engine import BacktestEngine


def generate_realistic_data(days: int, start_price: float = 100) -> pd.DataFrame:
    """Generate realistic market data with trends and volatility."""
    np.random.seed(42)  # For reproducibility
    
    dates = pd.date_range(end=datetime.now(), periods=days, freq="D")
    
    # Generate returns with regime changes
    returns = []
    regime = "bull"
    
    for i in range(days):
        # Regime switching
        if np.random.random() < 0.01:
            regime = "bear" if regime == "bull" else "bull"
        
        if regime == "bull":
            daily_return = np.random.randn() * 0.015 + 0.0005
        else:
            daily_return = np.random.randn() * 0.02 - 0.0003
        
        returns.append(daily_return)
    
    prices = start_price * np.cumprod(1 + np.array(returns))
    
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": prices * (1 + np.random.randn(days) * 0.003),
        "high": prices * (1 + np.abs(np.random.randn(days) * 0.01)),
        "low": prices * (1 - np.abs(np.random.randn(days) * 0.01)),
        "close": prices,
        "volume": np.random.randint(1000000, 50000000, days)
    })


class TestFullBacktestWorkflow:
    """Integration tests for complete backtest workflow."""
    
    @pytest.fixture
    def temp_cache(self):
        """Create temporary cache directory with test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(tmpdir)
            
            # Generate and save test data
            ndx_data = generate_realistic_data(500, start_price=10000)
            tqqq_data = generate_realistic_data(500, start_price=50)
            sqqq_data = generate_realistic_data(500, start_price=30)
            
            cache.save("NDX", ndx_data)
            cache.save("TQQQ", tqqq_data)
            cache.save("SQQQ", sqqq_data)
            
            yield tmpdir
    
    def test_full_backtest_workflow(self, temp_cache):
        """Test complete backtest from data load to results."""
        # Setup data manager with cached data
        data_config = {"cache_dir": temp_cache}
        data_manager = DataManager(data_config)
        data_manager.initialize()
        
        # Get data
        ndx_data = data_manager.get_data("NDX")
        tqqq_data = data_manager.get_data("TQQQ")
        sqqq_data = data_manager.get_data("SQQQ")
        
        # Initialize strategy
        aggregator = StrategyAggregator()
        
        # Run backtest
        engine = BacktestEngine({
            "initial_capital": 100000,
            "commission_per_trade": 0,
            "slippage_bps": 5
        })
        
        results = engine.run_backtest(
            ndx_data, tqqq_data, sqqq_data, aggregator
        )
        
        # Verify results
        assert results is not None
        assert "equity_curve" in results
        assert "metrics" in results
        assert "trades" in results
        
        # Verify equity curve
        equity = results["equity_curve"]
        assert len(equity) > 0
        assert equity["total_value"].iloc[0] <= 100000  # Should start at initial capital
        assert (equity["total_value"] >= 0).all()  # Never negative
        
        # Verify metrics
        metrics = results["metrics"]
        assert "total_return" in metrics
        assert "max_drawdown" in metrics
        assert "sharpe_ratio" in metrics
    
    def test_backtest_generates_trades(self, temp_cache):
        """Test that backtest generates trades."""
        data_config = {"cache_dir": temp_cache}
        data_manager = DataManager(data_config)
        data_manager.initialize()
        
        aggregator = StrategyAggregator()
        engine = BacktestEngine({"initial_capital": 100000})
        
        results = engine.run_backtest(
            data_manager.get_data("NDX"),
            data_manager.get_data("TQQQ"),
            data_manager.get_data("SQQQ"),
            aggregator
        )
        
        # Should have some trades
        assert len(results["trades"]) > 0
    
    def test_metrics_are_reasonable(self, temp_cache):
        """Test that metrics fall within reasonable bounds."""
        data_config = {"cache_dir": temp_cache}
        data_manager = DataManager(data_config)
        data_manager.initialize()
        
        aggregator = StrategyAggregator()
        engine = BacktestEngine({"initial_capital": 100000})
        
        results = engine.run_backtest(
            data_manager.get_data("NDX"),
            data_manager.get_data("TQQQ"),
            data_manager.get_data("SQQQ"),
            aggregator
        )
        
        metrics = results["metrics"]
        
        # Max drawdown should be between -100% and 0
        assert -1 <= metrics["max_drawdown"] <= 0
        
        # Sharpe ratio should be reasonable
        assert -5 <= metrics["sharpe_ratio"] <= 10
        
        # Win rate should be between 0 and 1
        assert 0 <= metrics.get("win_rate", 0) <= 1
