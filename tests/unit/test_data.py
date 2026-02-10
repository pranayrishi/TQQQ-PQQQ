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
from src.data.polygon_client import PolygonClient, PolygonAPIError


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
        
        assert loaded["date"].dtype == object  # String
        assert loaded["close"].dtype == float
        assert loaded["volume"].dtype == int


class TestPolygonClient:
    """Tests for PolygonClient (mock tests)."""
    
    def test_initialization_without_key(self):
        """Test that initialization without API key raises error."""
        with pytest.raises(ValueError):
            PolygonClient("")
    
    def test_initialization_with_key(self):
        """Test initialization with API key."""
        client = PolygonClient("test_api_key")
        assert client.api_key == "test_api_key"
    
    def test_rate_limit_delay(self):
        """Test rate limit delay is set."""
        client = PolygonClient("test_api_key")
        assert client.RATE_LIMIT_DELAY > 0
