"""
Cache Manager - Handles local data caching

Provides persistent storage of market data in CSV format
with automatic compression and validation.
"""

import os
import logging
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages local CSV cache for market data.
    
    Features:
    - Atomic writes (write to temp, then rename)
    - Automatic backup on update
    - Data validation on load
    """
    
    def __init__(self, cache_dir: str):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache files
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_path(self, ticker: str) -> str:
        """Get the file path for a ticker's cache."""
        return os.path.join(self.cache_dir, f"{ticker}.csv")
    
    def load(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Load cached data for a ticker.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            DataFrame if cache exists, None otherwise
        """
        path = self._get_path(ticker)
        
        if not os.path.exists(path):
            logger.debug(f"No cache file for {ticker}")
            return None
        
        try:
            df = pd.read_csv(path)
            
            # Ensure proper types
            df["date"] = df["date"].astype(str)
            df["volume"] = df["volume"].fillna(0).astype(int)
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)
            
            logger.debug(f"Loaded cache for {ticker}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error loading cache for {ticker}: {e}")
            return None
    
    def save(self, ticker: str, data: pd.DataFrame) -> bool:
        """
        Save data to cache.
        
        Args:
            ticker: Ticker symbol
            data: DataFrame to cache
            
        Returns:
            True if successful, False otherwise
        """
        path = self._get_path(ticker)
        temp_path = path + ".tmp"
        backup_path = path + ".bak"
        
        try:
            # Write to temp file first
            data.to_csv(temp_path, index=False)
            
            # Create backup of existing file
            if os.path.exists(path):
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(path, backup_path)
            
            # Atomic rename
            os.rename(temp_path, path)
            
            logger.info(f"Saved cache for {ticker}: {len(data)} rows")
            return True
            
        except Exception as e:
            logger.error(f"Error saving cache for {ticker}: {e}")
            
            # Cleanup temp file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return False
    
    def get_last_date(self, ticker: str) -> Optional[str]:
        """
        Get the last date in the cache for a ticker.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Last date string or None if no cache
        """
        df = self.load(ticker)
        if df is not None and not df.empty:
            return df["date"].max()
        return None
    
    def clear(self, ticker: str) -> bool:
        """
        Clear cache for a ticker.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            True if successful
        """
        path = self._get_path(ticker)
        
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Cleared cache for {ticker}")
            return True
        except Exception as e:
            logger.error(f"Error clearing cache for {ticker}: {e}")
            return False
    
    def clear_all(self) -> bool:
        """Clear all cached data."""
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".csv"):
                    os.remove(os.path.join(self.cache_dir, filename))
            logger.info("Cleared all cache")
            return True
        except Exception as e:
            logger.error(f"Error clearing all cache: {e}")
            return False
