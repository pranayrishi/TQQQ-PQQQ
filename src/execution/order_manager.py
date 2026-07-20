"""
Order Manager

Manages order placement across multiple broker accounts.
Provides unified interface for multi-broker execution.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Unified order management across multiple brokers.
    
    Handles:
    - Multiple broker connections
    - Order routing
    - Retry logic
    - Status tracking
    """
    
    def __init__(self, config: Dict):
        """
        Initialize order manager.
        
        Args:
            config: Configuration with broker settings
        """
        self.config = config
        self.brokers: Dict = {}
        self.account_broker_map: Dict[str, str] = {}
        self._orders: Dict[str, Dict] = {}
    
    def register_broker(self, name: str, broker) -> None:
        """
        Register a broker instance.
        
        Args:
            name: Broker identifier
            broker: Broker instance implementing BaseBroker interface
        """
        self.brokers[name] = broker
        logger.info(f"Registered broker: {name}")
    
    def connect_all(self) -> Dict[str, bool]:
        """Connect to all registered brokers."""
        results = {}
        
        for name, broker in self.brokers.items():
            try:
                success = broker.connect()
                results[name] = success
                
                if success:
                    # Map accounts to brokers
                    for account in broker.get_accounts():
                        self.account_broker_map[account["id"]] = name
                        
            except Exception as e:
                logger.error(f"Failed to connect to {name}: {e}")
                results[name] = False
        
        return results
    
    def disconnect_all(self) -> None:
        """Disconnect from all brokers."""
        for name, broker in self.brokers.items():
            try:
                broker.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {name}: {e}")
    
    def get_accounts(self) -> List[Dict]:
        """Get all accounts across all brokers."""
        accounts = []
        
        for name, broker in self.brokers.items():
            if broker.is_connected:
                for account in broker.get_accounts():
                    account["broker"] = name
                    accounts.append(account)
        
        return accounts
    
    def get_broker_for_account(self, account_id: str):
        """Get the broker instance for an account."""
        broker_name = self.account_broker_map.get(account_id)
        if not broker_name:
            raise ValueError(f"Unknown account: {account_id}")
        return self.brokers[broker_name]
    
    def get_portfolio_value(self, account_id: str) -> float:
        """Get portfolio value for an account."""
        broker = self.get_broker_for_account(account_id)
        return broker.get_portfolio_value(account_id)
    
    def get_positions(self, account_id: str) -> Dict[str, Dict]:
        """Get positions for an account."""
        broker = self.get_broker_for_account(account_id)
        return broker.get_positions(account_id)
    
    def get_cash_balance(self, account_id: str) -> float:
        """Get available cash for an account."""
        broker = self.get_broker_for_account(account_id)
        return broker.get_cash_balance(account_id)

    def get_quote(self, symbol: str) -> Dict:
        """Get a current quote from the first connected broker."""
        for broker in self.brokers.values():
            if broker.is_connected:
                return broker.get_quote(symbol)
        raise ConnectionError("No connected broker is available for quotes")

    def get_market_snapshots(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get current quotes, trades, and bars from a connected broker."""
        for broker in self.brokers.values():
            if broker.is_connected:
                return broker.get_market_snapshots(symbols)
        raise ConnectionError("No connected broker is available for market data")

    def get_market_clock(self) -> Dict:
        """Get the authoritative market clock from a connected broker."""
        for broker in self.brokers.values():
            if broker.is_connected:
                return broker.get_market_clock()
        raise ConnectionError("No connected broker is available for market clock")
    
    def place_order(
        self,
        account_id: str,
        symbol: str,
        shares: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        max_retries: int = 3
    ) -> Dict:
        """
        Place order with retry logic.
        
        Args:
            account_id: Target account
            symbol: Ticker symbol
            shares: Number of shares (positive=buy, negative=sell)
            order_type: Order type (market, limit)
            limit_price: Limit price if applicable
            max_retries: Maximum retry attempts
            
        Returns:
            Order result dictionary
        """
        broker = self.get_broker_for_account(account_id)
        
        last_error = None
        for attempt in range(max_retries):
            try:
                result = broker.place_order(
                    account_id=account_id,
                    symbol=symbol,
                    shares=shares,
                    order_type=order_type,
                    limit_price=limit_price
                )
                
                # Track order
                self._orders[result["order_id"]] = {
                    **result,
                    "account_id": account_id,
                    "broker": self.account_broker_map[account_id]
                }
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Order attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        raise last_error
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get status of an order."""
        if order_id not in self._orders:
            raise ValueError(f"Unknown order: {order_id}")
        
        order_info = self._orders[order_id]
        broker = self.brokers[order_info["broker"]]
        
        return broker.get_order_status(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if order_id not in self._orders:
            raise ValueError(f"Unknown order: {order_id}")
        
        order_info = self._orders[order_id]
        broker = self.brokers[order_info["broker"]]
        
        return broker.cancel_order(order_id)
    
    def get_pending_orders(self, account_id: Optional[str] = None) -> List[Dict]:
        """Get all pending orders."""
        pending = []
        
        for order_id, order in self._orders.items():
            if account_id and order["account_id"] != account_id:
                continue
            
            try:
                status = self.get_order_status(order_id)
                if status["status"] in ["pending", "open", "partial"]:
                    pending.append({**order, **status})
            except Exception as e:
                logger.warning(f"Could not get status for order {order_id}: {e}")
        
        return pending
    
    def cancel_all_orders(self, account_id: Optional[str] = None) -> Dict[str, bool]:
        """Cancel all pending orders."""
        results = {}
        
        for order in self.get_pending_orders(account_id):
            order_id = order["order_id"]
            try:
                results[order_id] = self.cancel_order(order_id)
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
                results[order_id] = False
        
        return results
