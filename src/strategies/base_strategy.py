"""
Base Strategy - Abstract base class for all strategies

Defines the interface that all strategies must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple
import pandas as pd
import numpy as np


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies.
    
    All strategies must implement the generate_signal method
    and provide configuration parameters.
    """
    
    def __init__(self, name: str, params: Dict):
        """
        Initialize strategy.
        
        Args:
            name: Strategy identifier
            params: Strategy-specific parameters
        """
        self.name = name
        self.params = params
        self._debug_info = {}
        self._validate_params()
    
    @abstractmethod
    def _validate_params(self) -> None:
        """Validate strategy parameters. Raise ValueError if invalid."""
        pass
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Tuple[float, float]:
        """
        Generate trading signal based on data.
        
        Args:
            data: DataFrame with OHLCV data (must include 'close' column)
            
        Returns:
            Tuple of (tqqq_position, sqqq_position) as floats from 0.0 to 1.0
            representing percentage of portfolio allocation
        """
        pass
    
    def get_debug_info(self) -> Dict:
        """
        Return debug information about current strategy state.
        
        Returns:
            Dictionary with strategy-specific debug data
        """
        return self._debug_info.copy()
    
    def calculate_moving_average(self, data: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
        """
        Calculate simple moving average.
        
        Args:
            data: DataFrame with price data
            period: MA period
            column: Column to calculate MA on
            
        Returns:
            Series with MA values
        """
        return data[column].rolling(window=period).mean()
    
    def calculate_ema(self, data: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
        """
        Calculate exponential moving average.
        
        Args:
            data: DataFrame with price data
            period: EMA period
            column: Column to calculate EMA on
            
        Returns:
            Series with EMA values
        """
        return data[column].ewm(span=period, adjust=False).mean()
    
    def calculate_rate_of_change(self, data: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
        """
        Calculate rate of change (ROC).
        
        Args:
            data: DataFrame with price data
            period: ROC period
            column: Column to calculate ROC on
            
        Returns:
            Series with ROC values (as decimal, not percentage)
        """
        return data[column].pct_change(periods=period)
    
    def calculate_momentum(self, data: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
        """
        Calculate momentum (price difference over period).
        
        Args:
            data: DataFrame with price data
            period: Momentum period
            column: Column to calculate momentum on
            
        Returns:
            Series with momentum values
        """
        return data[column].diff(periods=period)
    
    def calculate_volatility(self, data: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
        """
        Calculate rolling volatility (standard deviation of returns).
        
        Args:
            data: DataFrame with price data
            period: Volatility period
            column: Column to calculate volatility on
            
        Returns:
            Series with volatility values
        """
        returns = data[column].pct_change()
        return returns.rolling(window=period).std() * np.sqrt(252)  # Annualized
    
    def calculate_rsi(self, data: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            data: DataFrame with price data
            period: RSI period
            column: Column to calculate RSI on
            
        Returns:
            Series with RSI values (0-100)
        """
        delta = data[column].diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
