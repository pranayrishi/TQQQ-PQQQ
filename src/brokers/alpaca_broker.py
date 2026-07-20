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
        self.data_feed_name = config.get("data_feed", "iex").lower()
        
        self.client = None
        self.data_client = None
        self.data_feed = None
        self._account_id = None
    
    def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            from alpaca.data.enums import DataFeed
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.trading.client import TradingClient

            self.data_feed = DataFeed(self.data_feed_name)
            
            self.client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.paper
            )
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
            )
            
            # Verify connection by getting account
            account = self.client.get_account()
            self._account_id = account.id
            
            self._connected = True
            logger.info(f"Connected to Alpaca ({'paper' if self.paper else 'live'})")
            logger.info("Authenticated Alpaca account")
            
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
        self.data_client = None
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
        """Get the current quote plus trade/bar fallbacks for a symbol."""
        snapshot = self.get_market_snapshots([symbol]).get(symbol, {})
        quote = snapshot.get("latest_quote", {})
        trade = snapshot.get("latest_trade", {})
        minute_bar = snapshot.get("minute_bar", {})
        daily_bar = snapshot.get("daily_bar", {})
        return {
            "symbol": symbol,
            "bid": quote.get("bid", 0),
            "ask": quote.get("ask", 0),
            "bid_size": quote.get("bid_size", 0),
            "ask_size": quote.get("ask_size", 0),
            "timestamp": quote.get("timestamp"),
            "last_trade": trade.get("price", 0),
            "minute_close": minute_bar.get("close", 0),
            "daily_close": daily_bar.get("close", 0),
        }

    def get_market_snapshots(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get consolidated Alpaca snapshots for multiple stock symbols."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")
        
        try:
            from alpaca.data.requests import StockSnapshotRequest

            request = StockSnapshotRequest(
                symbol_or_symbols=symbols,
                feed=self.data_feed,
            )
            snapshots = self.data_client.get_stock_snapshot(request)
            return {
                symbol: self._snapshot_to_dict(snapshot)
                for symbol, snapshot in snapshots.items()
            }
        except Exception as e:
            logger.error(f"Failed to get market snapshots for {symbols}: {e}")
            raise

    @staticmethod
    def _snapshot_to_dict(snapshot) -> Dict:
        """Convert Alpaca snapshot models into plain dictionaries."""
        quote = snapshot.latest_quote
        trade = snapshot.latest_trade

        def bar_to_dict(bar) -> Dict:
            if bar is None:
                return {}
            return {
                "timestamp": str(bar.timestamp),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
                "trade_count": int(bar.trade_count or 0),
                "vwap": float(bar.vwap) if bar.vwap is not None else None,
            }

        return {
            "latest_quote": {
                "timestamp": str(quote.timestamp) if quote else None,
                "bid": float(quote.bid_price) if quote else 0,
                "ask": float(quote.ask_price) if quote else 0,
                "bid_size": int(quote.bid_size) if quote else 0,
                "ask_size": int(quote.ask_size) if quote else 0,
            },
            "latest_trade": {
                "timestamp": str(trade.timestamp) if trade else None,
                "price": float(trade.price) if trade else 0,
                "size": float(trade.size) if trade else 0,
            },
            "minute_bar": bar_to_dict(snapshot.minute_bar),
            "daily_bar": bar_to_dict(snapshot.daily_bar),
            "previous_daily_bar": bar_to_dict(snapshot.previous_daily_bar),
        }

    def get_market_clock(self) -> Dict:
        """Get Alpaca's authoritative market clock."""
        if not self._connected:
            raise ConnectionError("Not connected to Alpaca")

        clock = self.client.get_clock()
        return {
            "timestamp": str(clock.timestamp),
            "is_open": bool(clock.is_open),
            "next_open": str(clock.next_open),
            "next_close": str(clock.next_close),
        }
    
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
