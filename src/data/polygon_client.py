"""
Polygon.io API Client for Market Data

This module handles all communication with Polygon.io for fetching
historical and real-time market data.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import requests
import pandas as pd

logger = logging.getLogger(__name__)


class PolygonAPIError(Exception):
    """Custom exception for Polygon API errors."""
    pass


class PolygonClient:
    """
    Client for Polygon.io market data API.
    
    Handles rate limiting, retries, and data validation automatically.
    """
    
    BASE_URL = "https://api.polygon.io"
    RATE_LIMIT_DELAY = 0.25  # 4 requests per second for free tier
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    
    def __init__(self, api_key: str):
        """
        Initialize Polygon client.
        
        Args:
            api_key: Polygon.io API key
        """
        if not api_key:
            raise ValueError("Polygon API key is required")
        
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}"
        })
        self._last_request_time = 0
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict:
        """
        Make API request with retry logic.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response as dictionary
            
        Raises:
            PolygonAPIError: If request fails after retries
        """
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}
        
        for attempt in range(self.MAX_RETRIES):
            self._rate_limit()
            
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    logger.warning(f"Rate limited, waiting {self.RETRY_DELAY}s...")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        raise PolygonAPIError(f"Failed to fetch data from {endpoint} after {self.MAX_RETRIES} attempts")
    
    def get_daily_bars(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        adjusted: bool = True
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV bars for a ticker.
        
        Args:
            ticker: Stock/ETF ticker symbol (e.g., "TQQQ", "I:NDX" for index)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            adjusted: Whether to return split/dividend adjusted prices
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        # For indices, Polygon uses "I:" prefix
        polygon_ticker = f"I:{ticker}" if ticker == "NDX" else ticker
        
        endpoint = f"/v2/aggs/ticker/{polygon_ticker}/range/1/day/{start_date}/{end_date}"
        params = {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": 50000
        }
        
        all_results = []
        
        while True:
            data = self._make_request(endpoint, params)
            
            if "results" in data and data["results"]:
                all_results.extend(data["results"])
                
                # Check for pagination
                if "next_url" in data:
                    endpoint = data["next_url"].replace(self.BASE_URL, "")
                    params = {}
                else:
                    break
            else:
                break
        
        if not all_results:
            logger.warning(f"No data returned for {ticker} from {start_date} to {end_date}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_results)
        
        # Rename columns
        rename_map = {
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
        }
        if "v" in df.columns:
            rename_map["v"] = "volume"
        
        df = df.rename(columns=rename_map)
        
        # Convert timestamp to date
        df["date"] = pd.to_datetime(df["timestamp"], unit="ms").dt.strftime("%Y-%m-%d")
        
        # Add volume column if missing (indices like NDX don't have volume)
        if "volume" not in df.columns:
            df["volume"] = 0
        
        # Select and order columns
        df = df[["date", "open", "high", "low", "close", "volume"]]
        
        # Ensure proper types
        df["volume"] = df["volume"].fillna(0).astype(int)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float).round(4)
        
        logger.info(f"Fetched {len(df)} bars for {ticker}")
        return df
    
    def get_latest_price(self, ticker: str) -> Dict[str, float]:
        """
        Get the latest price data for a ticker.
        
        Args:
            ticker: Stock/ETF ticker symbol
            
        Returns:
            Dictionary with current price data
        """
        polygon_ticker = f"I:{ticker}" if ticker == "NDX" else ticker
        endpoint = f"/v2/last/trade/{polygon_ticker}"
        
        data = self._make_request(endpoint)
        
        if "results" in data:
            return {
                "price": data["results"].get("p", 0),
                "size": data["results"].get("s", 0),
                "timestamp": data["results"].get("t", 0)
            }
        
        raise PolygonAPIError(f"Could not get latest price for {ticker}")
    
    def get_previous_close(self, ticker: str) -> Dict[str, Any]:
        """
        Get previous day's closing data.
        
        Args:
            ticker: Stock/ETF ticker symbol
            
        Returns:
            Dictionary with previous close data
        """
        polygon_ticker = f"I:{ticker}" if ticker == "NDX" else ticker
        endpoint = f"/v2/aggs/ticker/{polygon_ticker}/prev"
        
        data = self._make_request(endpoint)
        
        if "results" in data and data["results"]:
            result = data["results"][0]
            return {
                "date": datetime.fromtimestamp(result["t"] / 1000).strftime("%Y-%m-%d"),
                "open": result["o"],
                "high": result["h"],
                "low": result["l"],
                "close": result["c"],
                "volume": result.get("v", 0)
            }
        
        raise PolygonAPIError(f"Could not get previous close for {ticker}")
