"""
Data Manager - Orchestrates all data operations

Handles fetching, caching, validation, and providing data to strategies.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import pandas as pd

from .yfinance_client import YahooFinanceClient, YahooFinanceError
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


class DataError(Exception):
    """Custom exception for data errors."""
    pass


class DataManager:
    """
    Central data management for the trading system.
    
    Responsibilities:
    - Fetch adjusted historical data through yfinance
    - Maintain local CSV cache
    - Provide fallback when API is unavailable
    - Validate data integrity
    """
    
    REQUIRED_TICKERS = ["NDX", "TQQQ", "SQQQ"]
    
    # Historical start dates for each ticker
    TICKER_START_DATES = {
        "NDX": "1985-01-01",   # NASDAQ-100 index inception
        "TQQQ": "2010-02-11",  # TQQQ inception date
        "SQQQ": "2010-02-11"   # SQQQ inception date
    }
    
    def __init__(self, config: Dict):
        """
        Initialize DataManager.
        
        Args:
            config: Configuration dictionary containing data paths
        """
        self.config = config
        self.cache_dir = config.get("cache_dir", "data/cache")
        
        self.market_data = YahooFinanceClient()
        
        # Initialize cache manager
        self.cache = CacheManager(self.cache_dir)
        
        # Data storage
        self._data: Dict[str, pd.DataFrame] = {}
    
    def initialize(self) -> None:
        """
        Initialize data for all required tickers.
        
        Loads from cache and updates with latest data from API.
        """
        logger.info("Initializing data manager...")
        
        for ticker in self.REQUIRED_TICKERS:
            self._load_ticker_data(ticker)
        
        logger.info("Data initialization complete")
    
    def _load_ticker_data(self, ticker: str) -> None:
        """
        Load data for a single ticker.
        
        Args:
            ticker: Ticker symbol to load
        """
        # First, try to load from cache
        cached_data = self.cache.load(ticker)
        
        if cached_data is not None and not cached_data.empty:
            logger.info(f"Loaded {len(cached_data)} cached rows for {ticker}")
            last_date = cached_data["date"].max()
            
            # Check if we need to update
            today = datetime.now().strftime("%Y-%m-%d")
            
            if last_date < today:
                # Fetch new data
                start_date = (datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                
                try:
                    new_data = self.market_data.get_daily_bars(
                        ticker,
                        start_date,
                        today,
                    )
                    
                    if not new_data.empty:
                        # Combine and deduplicate
                        combined = pd.concat([cached_data, new_data], ignore_index=True)
                        combined = combined.drop_duplicates(subset=["date"], keep="last")
                        combined = combined.sort_values("date").reset_index(drop=True)
                        
                        # Save updated cache
                        self.cache.save(ticker, combined)
                        self._data[ticker] = combined
                        logger.info(f"Updated {ticker} with {len(new_data)} new rows")
                        return
                        
                except YahooFinanceError as e:
                    logger.warning(f"Could not update {ticker}: {e}")
            
            self._data[ticker] = cached_data
            
        else:
            # No cache - fetch full history
            logger.info(f"No cache for {ticker}, fetching full history...")
            
            start_date = self.TICKER_START_DATES.get(ticker, "2010-01-01")
            end_date = datetime.now().strftime("%Y-%m-%d")
            
            try:
                data = self.market_data.get_daily_bars(ticker, start_date, end_date)
                
                if not data.empty:
                    self.cache.save(ticker, data)
                    self._data[ticker] = data
                    logger.info(f"Fetched and cached {len(data)} rows for {ticker}")
                else:
                    raise DataError(f"No data available for {ticker}")
                    
            except YahooFinanceError as e:
                raise DataError(f"Failed to fetch data for {ticker}: {e}")
    
    def get_data(self, ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Get OHLCV data for a ticker.
        
        Args:
            ticker: Ticker symbol
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            DataFrame with OHLCV data
        """
        if ticker not in self._data:
            raise DataError(f"Data not loaded for {ticker}")
        
        df = self._data[ticker].copy()
        
        if start_date:
            df = df[df["date"] >= start_date]
        if end_date:
            df = df[df["date"] <= end_date]
        
        return df
    
    def get_latest_bar(self, ticker: str) -> Dict:
        """
        Get the most recent bar for a ticker.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dictionary with latest OHLCV data
        """
        df = self.get_data(ticker)
        
        if df.empty:
            raise DataError(f"No data available for {ticker}")
        
        latest = df.iloc[-1]
        return {
            "date": latest["date"],
            "open": latest["open"],
            "high": latest["high"],
            "low": latest["low"],
            "close": latest["close"],
            "volume": latest["volume"]
        }
    
    def refresh_intraday(self) -> None:
        """
        Refresh with latest intraday data.
        
        Called during the execution window to get current prices.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        for ticker in self.REQUIRED_TICKERS:
            try:
                last_date = self._data[ticker]["date"].iloc[-1]
                start_date = (
                    datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)
                ).strftime("%Y-%m-%d")
                new_data = self.market_data.get_daily_bars(
                    ticker,
                    start_date,
                    today,
                )
                
                if not new_data.empty:
                    combined = pd.concat(
                        [self._data[ticker], new_data], ignore_index=True
                    )
                    combined = combined.drop_duplicates(subset=["date"], keep="last")
                    combined = combined.sort_values("date").reset_index(drop=True)
                    self._data[ticker] = combined
                    self.cache.save(ticker, combined)
                    logger.info(f"Refreshed latest available data for {ticker}")
                    
            except YahooFinanceError as e:
                logger.warning(f"Could not refresh {ticker}: {e}")
    
    def validate_data(self, ticker: str) -> bool:
        """
        Validate data integrity for a ticker.
        
        Args:
            ticker: Ticker symbol to validate
            
        Returns:
            True if data is valid, False otherwise
        """
        if ticker not in self._data:
            return False
        
        df = self._data[ticker]
        
        # Check for required columns
        required_cols = ["date", "open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            logger.error(f"{ticker}: Missing required columns")
            return False
        
        # Check for nulls in price data
        if df[["open", "high", "low", "close"]].isnull().any().any():
            logger.error(f"{ticker}: Contains null price values")
            return False
        
        # Check price sanity (high >= low)
        if (df["high"] < df["low"]).any():
            logger.error(f"{ticker}: Found high < low")
            return False
        
        # Check for duplicate dates
        if df["date"].duplicated().any():
            logger.error(f"{ticker}: Contains duplicate dates")
            return False
        
        # Check date ordering
        dates = pd.to_datetime(df["date"])
        if not dates.is_monotonic_increasing:
            logger.error(f"{ticker}: Dates not in ascending order")
            return False
        
        logger.info(f"{ticker}: Data validation passed")
        return True
    
    def get_aligned_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Get data for all tickers aligned by date.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary mapping ticker to DataFrame
        """
        result = {}
        
        for ticker in self.REQUIRED_TICKERS:
            result[ticker] = self.get_data(ticker, start_date, end_date)
        
        return result
    
    @property
    def is_initialized(self) -> bool:
        """Check if all required data is loaded."""
        return all(ticker in self._data for ticker in self.REQUIRED_TICKERS)
