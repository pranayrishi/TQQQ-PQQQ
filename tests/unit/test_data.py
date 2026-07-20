"""
Unit tests for data infrastructure.
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
from datetime import datetime

from src.data.cache_manager import CacheManager
from src.data.yfinance_client import YahooFinanceClient


class TestCacheManager:
    """Tests for CacheManager."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create cache manager with temp directory."""
        return CacheManager(temp_cache_dir)
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample OHLCV data."""
        dates = pd.date_range(end=datetime.now(), periods=100, freq="D")
        return pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "open": np.random.rand(100) * 100 + 50,
            "high": np.random.rand(100) * 100 + 60,
            "low": np.random.rand(100) * 100 + 40,
            "close": np.random.rand(100) * 100 + 50,
            "volume": np.random.randint(1000000, 10000000, 100)
        })
    
    def test_save_and_load(self, cache_manager, sample_data):
        """Test saving and loading data."""
        ticker = "TEST"
        
        # Save
        result = cache_manager.save(ticker, sample_data)
        assert result is True
        
        # Load
        loaded = cache_manager.load(ticker)
        assert loaded is not None
        assert len(loaded) == len(sample_data)
    
    def test_load_nonexistent(self, cache_manager):
        """Test loading non-existent ticker."""
        loaded = cache_manager.load("NONEXISTENT")
        assert loaded is None

    def test_loads_backup_when_primary_is_missing(
        self,
        cache_manager,
        sample_data,
    ):
        """Tracked backup caches can bootstrap a fresh runner."""
        backup_path = cache_manager._get_path("TEST") + ".bak"
        sample_data.to_csv(backup_path, index=False)

        loaded = cache_manager.load("TEST")

        assert loaded is not None
        assert len(loaded) == len(sample_data)
    
    def test_get_last_date(self, cache_manager, sample_data):
        """Test getting last date from cache."""
        ticker = "TEST"
        cache_manager.save(ticker, sample_data)
        
        last_date = cache_manager.get_last_date(ticker)
        assert last_date == sample_data["date"].max()
    
    def test_clear(self, cache_manager, sample_data):
        """Test clearing cache."""
        ticker = "TEST"
        cache_manager.save(ticker, sample_data)
        
        result = cache_manager.clear(ticker)
        assert result is True
        
        loaded = cache_manager.load(ticker)
        assert loaded is None
    
    def test_data_types_preserved(self, cache_manager, sample_data):
        """Test that data types are preserved through save/load."""
        ticker = "TEST"
        cache_manager.save(ticker, sample_data)
        
        loaded = cache_manager.load(ticker)
        
        assert pd.api.types.is_string_dtype(loaded["date"].dtype)
        assert loaded["close"].dtype == float
        assert loaded["volume"].dtype == int


class TestYahooFinanceClient:
    """Tests for yfinance data normalization."""

    def test_symbol_mapping(self):
        assert YahooFinanceClient.SYMBOLS["NDX"] == "^NDX"
        assert YahooFinanceClient.SYMBOLS["TQQQ"] == "TQQQ"

    def test_normalize_daily_bars(self):
        raw = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1200],
            },
            index=pd.to_datetime(["2026-07-16", "2026-07-17"]),
        )

        result = YahooFinanceClient._normalize(
            raw,
            "TQQQ",
            "2026-07-16",
            "2026-07-17",
        )

        assert list(result.columns) == [
            "date", "open", "high", "low", "close", "volume"
        ]
        assert result["date"].tolist() == ["2026-07-16", "2026-07-17"]
        assert result["close"].tolist() == [101.0, 102.0]

    def test_rejects_unknown_ticker(self):
        with pytest.raises(ValueError, match="Unsupported"):
            YahooFinanceClient().get_daily_bars(
                "UNKNOWN",
                "2026-07-16",
                "2026-07-17",
            )
