"""
Alpaca Broker Integration

Implements the BaseBroker interface for Alpaca trading API.
Supports both paper and live trading modes.
"""

import logging
from typing import Dict, List, Optional

from .base_broker import BaseBroker

logger = logging.getLogger(__name__)


class AlpacaBroker(BaseBroker):
    """
    Alpaca broker integration.
    
    Features:
    - Paper and live trading support
    - Fractional shares support
    - Market and limit orders
    """
    
    def __init__(self, config: Dict):
        """
        Initialize Alpaca broker.
        
        Args:
            config: Configuration with api_key, api_secret, and paper flag
        """
        super().__init__(config)
        
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.paper = config.get("paper", True)
        
        self.client = None
        self._account_id = None
    
    def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            from alpaca.trading.client import TradingClient
            
            self.client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.paper
            )
            
            # Verify connection by getting account
            account = self.client.get_account()
            self._account_id = account.id
            
            self._connected = True
            logger.info(f"Connected to Alpaca ({'paper' if self.paper else 'live'})")
            logger.info(f"Account: {self._account_id}")
            
            return True
            
        except ImportError:
            logger.error("alpaca-py package not installed. Install with: pip install alpaca-py")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Alpaca API."""
        self.client = None
        self._connected = False
        logger.info("Disconnected from Alpaca")
    
    def get_accounts(self) -> List[Dict]:
        """Get list of accounts (Alpaca has single account per API key)."""
        if not self._connected:
            return []
        
        account = self.client.get_account()
        
        return [{
            "id": account.id,
            "name": f"Alpaca {'Paper' if self.paper else 'Live'}",
            "status": account.status.value,
            "currency": account.currency,
            "buying_power": float(account.buying_power),
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value)
        }]
    
    def get_portfolio_value(self, account_id: str) -> float:
        """Get total portfolio value."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        account = self.client.get_account()
        return float(account.portfolio_value)
    
    def get_cash_balance(self, account_id: str) -> float:
        """Get available cash balance."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        account = self.client.get_account()
        return float(account.cash)
    
    def get_positions(self, account_id: str) -> Dict[str, Dict]:
        """Get current positions."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        positions = self.client.get_all_positions()
        
        result = {}
        for pos in positions:
            result[pos.symbol] = {
                "symbol": pos.symbol,
                "shares": float(pos.qty),
                "avg_cost": float(pos.avg_entry_price),
                "market_value": float(pos.market_value),
                "unrealized_pl": float(pos.unrealized_pl),
                "unrealized_pl_pct": float(pos.unrealized_plpc),
                "current_price": float(pos.current_price),
                "side": pos.side.value
            }
        
        return result
    
    def place_order(
        self,
        account_id: str,
        symbol: str,
        shares: float,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Dict:
        """Place an order."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        # Determine side
        if shares > 0:
            side = OrderSide.BUY
            qty = abs(shares)
        else:
            side = OrderSide.SELL
            qty = abs(shares)
        
        try:
            if order_type == "market":
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    time_in_force=TimeInForce.DAY
                )
            elif order_type == "limit":
                if limit_price is None:
                    raise ValueError("Limit price required for limit orders")
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price
                )
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            order = self.client.submit_order(order_request)
            
            result = {
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "qty": float(order.qty),
                "type": order.type.value,
                "status": order.status.value,
                "submitted_at": str(order.submitted_at)
            }
            
            logger.info(f"Order placed: {result['order_id']} - {side.value} {qty} {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Order failed: {e}")
            raise
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get status of an order."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        order = self.client.get_order_by_id(order_id)
        
        return {
            "order_id": order.id,
            "status": order.status.value,
            "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "submitted_at": str(order.submitted_at),
            "filled_at": str(order.filled_at) if order.filled_at else None
        }
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        try:
            self.client.cancel_order_by_id(order_id)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_quote(self, symbol: str) -> Dict:
        """Get current quote for a symbol."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        try:
            from alpaca.data.live import StockDataStream
            from alpaca.data.requests import StockLatestQuoteRequest
            from alpaca.data.historical import StockHistoricalDataClient
            
            data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.api_secret
            )
            
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = data_client.get_stock_latest_quote(request)
            
            if symbol in quote:
                q = quote[symbol]
                return {
                    "symbol": symbol,
                    "bid": float(q.bid_price),
                    "ask": float(q.ask_price),
                    "bid_size": int(q.bid_size),
                    "ask_size": int(q.ask_size),
                    "timestamp": str(q.timestamp)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            raise
    
    def get_order_history(self, account_id: str, days: int = 30) -> List[Dict]:
        """Get order history."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        from datetime import datetime, timedelta
        
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            after=datetime.now() - timedelta(days=days)
        )
        
        orders = self.client.get_orders(request)
        
        return [
            {
                "order_id": o.id,
                "symbol": o.symbol,
                "side": o.side.value,
                "qty": float(o.qty),
                "filled_qty": float(o.filled_qty) if o.filled_qty else 0,
                "type": o.type.value,
                "status": o.status.value,
                "submitted_at": str(o.submitted_at),
                "filled_at": str(o.filled_at) if o.filled_at else None
            }
            for o in orders
        ]
