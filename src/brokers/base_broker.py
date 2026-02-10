"""
Base Broker - Abstract base class for broker integrations

Defines the interface that all broker implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseBroker(ABC):
    """
    Abstract base class for broker integrations.
    
    All broker implementations must implement these methods
    to ensure consistent behavior across different brokers.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize broker.
        
        Args:
            config: Broker-specific configuration
        """
        self.config = config
        self._connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to broker API.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker API."""
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected
    
    @abstractmethod
    def get_accounts(self) -> List[Dict]:
        """
        Get list of available accounts.
        
        Returns:
            List of account dictionaries with at least 'id' and 'name' keys
        """
        pass
    
    @abstractmethod
    def get_portfolio_value(self, account_id: str) -> float:
        """
        Get total portfolio value for an account.
        
        Args:
            account_id: Account identifier
            
        Returns:
            Total portfolio value
        """
        pass
    
    @abstractmethod
    def get_cash_balance(self, account_id: str) -> float:
        """
        Get available cash balance.
        
        Args:
            account_id: Account identifier
            
        Returns:
            Available cash
        """
        pass
    
    @abstractmethod
    def get_positions(self, account_id: str) -> Dict[str, Dict]:
        """
        Get current positions.
        
        Args:
            account_id: Account identifier
            
        Returns:
            Dictionary mapping symbol to position details
        """
        pass
    
    @abstractmethod
    def place_order(
        self,
        account_id: str,
        symbol: str,
        shares: float,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Dict:
        """
        Place an order.
        
        Args:
            account_id: Account identifier
            symbol: Ticker symbol
            shares: Number of shares (positive=buy, negative=sell)
            order_type: Order type (market, limit)
            limit_price: Limit price for limit orders
            
        Returns:
            Order result with at least 'order_id' and 'status' keys
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict:
        """
        Get status of an order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order status dictionary
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            True if cancellation successful
        """
        pass
    
    def get_quote(self, symbol: str) -> Dict:
        """
        Get current quote for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Quote dictionary with bid, ask, last price
        """
        raise NotImplementedError("Quote functionality not implemented")
    
    def get_order_history(self, account_id: str, days: int = 30) -> List[Dict]:
        """
        Get order history for an account.
        
        Args:
            account_id: Account identifier
            days: Number of days of history
            
        Returns:
            List of historical orders
        """
        raise NotImplementedError("Order history not implemented")
