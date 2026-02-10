"""
Unit tests for backtesting engine.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.backtest.backtest_engine import BacktestEngine
from src.backtest.performance_metrics import PerformanceMetrics
from src.strategies.strategy_aggregator import StrategyAggregator


def generate_test_data(days: int, ticker: str = "NDX") -> pd.DataFrame:
    """Generate test OHLCV data."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="D")
    
    # Generate random walk with slight upward drift
    returns = np.random.randn(days) * 0.02 + 0.0003
    prices = 100 * np.cumprod(1 + returns)
    
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": prices * (1 + np.random.randn(days) * 0.002),
        "high": prices * (1 + np.abs(np.random.randn(days) * 0.01)),
        "low": prices * (1 - np.abs(np.random.randn(days) * 0.01)),
        "close": prices,
        "volume": np.random.randint(1000000, 10000000, days)
    })


class TestBacktestEngine:
    """Tests for BacktestEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create backtest engine."""
        config = {
            "initial_capital": 100000,
            "commission_per_trade": 0,
            "slippage_bps": 0
        }
        return BacktestEngine(config)
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample data for all tickers."""
        return {
            "ndx": generate_test_data(500, "NDX"),
            "tqqq": generate_test_data(500, "TQQQ"),
            "sqqq": generate_test_data(500, "SQQQ")
        }
    
    def test_initialization(self, engine):
        """Test engine initialization."""
        assert engine.initial_capital == 100000
        assert engine.cash == 100000
    
    def test_backtest_runs(self, engine, sample_data):
        """Test that backtest completes."""
        aggregator = StrategyAggregator()
        
        results = engine.run_backtest(
            sample_data["ndx"],
            sample_data["tqqq"],
            sample_data["sqqq"],
            aggregator
        )
        
        assert results is not None
        assert "equity_curve" in results
        assert "metrics" in results
    
    def test_equity_curve_structure(self, engine, sample_data):
        """Test equity curve has expected columns."""
        aggregator = StrategyAggregator()
        
        results = engine.run_backtest(
            sample_data["ndx"],
            sample_data["tqqq"],
            sample_data["sqqq"],
            aggregator
        )
        
        equity = results["equity_curve"]
        required_columns = ["date", "total_value", "cash", "position"]
        
        for col in required_columns:
            assert col in equity.columns
    
    def test_no_negative_equity(self, engine, sample_data):
        """Test that equity never goes negative."""
        aggregator = StrategyAggregator()
        
        results = engine.run_backtest(
            sample_data["ndx"],
            sample_data["tqqq"],
            sample_data["sqqq"],
            aggregator
        )
        
        assert (results["equity_curve"]["total_value"] >= 0).all()
    
    def test_date_filtering(self, engine, sample_data):
        """Test date filtering in backtest."""
        aggregator = StrategyAggregator()
        
        # Get middle date range
        dates = sample_data["ndx"]["date"]
        start = dates.iloc[100]
        end = dates.iloc[300]
        
        results = engine.run_backtest(
            sample_data["ndx"],
            sample_data["tqqq"],
            sample_data["sqqq"],
            aggregator,
            start_date=start,
            end_date=end
        )
        
        equity_dates = results["equity_curve"]["date"]
        assert equity_dates.min() >= start
        assert equity_dates.max() <= end


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics."""
    
    @pytest.fixture
    def sample_equity(self):
        """Generate sample equity curve."""
        days = 252
        dates = pd.date_range(end=datetime.now(), periods=days, freq="D")
        
        # Simulate growing equity with drawdowns
        returns = np.random.randn(days) * 0.02 + 0.001
        values = 100000 * np.cumprod(1 + returns)
        
        return pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "total_value": values
        })
    
    def test_initialization(self, sample_equity):
        """Test metrics initialization."""
        metrics = PerformanceMetrics(sample_equity, 100000)
        assert metrics.initial_capital == 100000
    
    def test_total_return(self, sample_equity):
        """Test total return calculation."""
        metrics = PerformanceMetrics(sample_equity, 100000)
        result = metrics.get_metrics()
        
        expected = (sample_equity["total_value"].iloc[-1] - 100000) / 100000
        assert abs(result["total_return"] - expected) < 0.001
    
    def test_max_drawdown(self, sample_equity):
        """Test max drawdown is negative or zero."""
        metrics = PerformanceMetrics(sample_equity, 100000)
        result = metrics.get_metrics()
        
        assert result["max_drawdown"] <= 0
    
    def test_sharpe_ratio(self, sample_equity):
        """Test Sharpe ratio calculation."""
        metrics = PerformanceMetrics(sample_equity, 100000)
        result = metrics.get_metrics()
        
        # Sharpe should be a reasonable number
        assert -10 < result["sharpe_ratio"] < 10
    
    def test_summary_string(self, sample_equity):
        """Test summary generation."""
        metrics = PerformanceMetrics(sample_equity, 100000)
        summary = metrics.get_summary()
        
        assert "Total Return" in summary
        assert "CAGR" in summary
        assert "Max Drawdown" in summary
    
    def test_to_dataframe(self, sample_equity):
        """Test DataFrame export."""
        metrics = PerformanceMetrics(sample_equity, 100000)
        df = metrics.to_dataframe()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
