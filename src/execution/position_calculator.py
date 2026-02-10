"""
Position Calculator

Calculates required trades to reach target portfolio allocations.
Handles fractional shares, minimum trade values, and position limits.
"""

import logging
from typing import Dict, Optional
import math

logger = logging.getLogger(__name__)


class PositionCalculator:
    """
    Calculates required trades for portfolio rebalancing.
    
    Features:
    - Support for fractional shares
    - Minimum trade value filtering
    - Position limit enforcement
    - Commission-aware calculations
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize position calculator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.allow_fractional = self.config.get("allow_fractional_shares", True)
        self.min_trade_value = self.config.get("min_trade_value", 10.0)
        self.commission = self.config.get("commission_per_trade", 0.0)
    
    def calculate_required_trades(
        self,
        portfolio_value: float,
        current_holdings: Dict[str, float],
        target_percentages: Dict[str, float],
        current_prices: Dict[str, float]
    ) -> Dict[str, Dict]:
        """
        Calculate trades needed to reach target allocations.
        
        Args:
            portfolio_value: Total portfolio value
            current_holdings: Current shares held {symbol: shares}
            target_percentages: Target allocations {symbol: pct (0-1)}
            current_prices: Current prices {symbol: price}
            
        Returns:
            Dictionary with trade details for each symbol
        """
        trades = {}
        
        for symbol in set(current_holdings.keys()) | set(target_percentages.keys()):
            current_shares = current_holdings.get(symbol, 0)
            target_pct = target_percentages.get(symbol, 0)
            price = current_prices.get(symbol, 0)
            
            if price <= 0:
                logger.warning(f"Invalid price for {symbol}: {price}")
                trades[symbol] = {
                    "action": "SKIP",
                    "reason": "Invalid price",
                    "current_shares": current_shares,
                    "target_shares": 0,
                    "shares_to_trade": 0,
                    "trade_value": 0
                }
                continue
            
            # Calculate target shares
            target_value = portfolio_value * target_pct
            target_shares = target_value / price
            
            # Round if not allowing fractional shares
            if not self.allow_fractional:
                target_shares = int(target_shares)
            
            # Calculate trade
            shares_to_trade = target_shares - current_shares
            trade_value = abs(shares_to_trade * price)
            
            # Determine action
            if abs(shares_to_trade) < 0.001:  # Essentially zero
                action = "HOLD"
            elif trade_value < self.min_trade_value:
                action = "HOLD"
                shares_to_trade = 0
            elif shares_to_trade > 0:
                action = "BUY"
            else:
                action = "SELL"
                shares_to_trade = abs(shares_to_trade)  # Make positive for selling
            
            # Calculate current and target values
            current_value = current_shares * price
            
            trades[symbol] = {
                "action": action,
                "current_shares": current_shares,
                "current_value": current_value,
                "current_pct": current_value / portfolio_value if portfolio_value > 0 else 0,
                "target_shares": target_shares,
                "target_value": target_value,
                "target_pct": target_pct,
                "shares_to_trade": shares_to_trade if action == "BUY" else -shares_to_trade if action == "SELL" else 0,
                "trade_value": trade_value if action != "HOLD" else 0,
                "price": price,
                "estimated_commission": self.commission if action != "HOLD" else 0
            }
        
        logger.info(f"Calculated trades: {self._summarize_trades(trades)}")
        return trades
    
    def _summarize_trades(self, trades: Dict[str, Dict]) -> str:
        """Create a summary string for trades."""
        summaries = []
        for symbol, trade in trades.items():
            if trade["action"] != "HOLD":
                summaries.append(f"{trade['action']} {abs(trade['shares_to_trade']):.2f} {symbol}")
        return ", ".join(summaries) if summaries else "No trades needed"
    
    def calculate_cash_needed(self, trades: Dict[str, Dict]) -> float:
        """
        Calculate net cash needed for all trades.
        
        Args:
            trades: Trade dictionary from calculate_required_trades
            
        Returns:
            Net cash needed (positive = need cash, negative = will receive cash)
        """
        net_cash = 0.0
        
        for symbol, trade in trades.items():
            if trade["action"] == "BUY":
                net_cash += trade["trade_value"] + trade["estimated_commission"]
            elif trade["action"] == "SELL":
                net_cash -= trade["trade_value"] - trade["estimated_commission"]
        
        return net_cash
    
    def validate_trades(
        self,
        trades: Dict[str, Dict],
        available_cash: float,
        max_position_value: Optional[float] = None
    ) -> Dict[str, Dict]:
        """
        Validate and adjust trades based on constraints.
        
        Args:
            trades: Calculated trades
            available_cash: Available cash for trading
            max_position_value: Maximum value for any single position
            
        Returns:
            Validated trades dictionary
        """
        validated = {}
        
        # First pass - collect sells to add to available cash
        sell_proceeds = 0.0
        for symbol, trade in trades.items():
            if trade["action"] == "SELL":
                sell_proceeds += trade["trade_value"] - trade["estimated_commission"]
        
        total_available = available_cash + sell_proceeds
        
        # Second pass - validate buys
        for symbol, trade in trades.items():
            validated[symbol] = trade.copy()
            
            if trade["action"] == "BUY":
                cost = trade["trade_value"] + trade["estimated_commission"]
                
                # Check cash constraint
                if cost > total_available:
                    # Scale down the buy
                    max_shares = (total_available - trade["estimated_commission"]) / trade["price"]
                    if not self.allow_fractional:
                        max_shares = int(max_shares)
                    
                    if max_shares <= 0:
                        validated[symbol]["action"] = "HOLD"
                        validated[symbol]["shares_to_trade"] = 0
                        validated[symbol]["trade_value"] = 0
                        validated[symbol]["reason"] = "Insufficient cash"
                    else:
                        validated[symbol]["shares_to_trade"] = max_shares
                        validated[symbol]["trade_value"] = max_shares * trade["price"]
                        validated[symbol]["target_shares"] = trade["current_shares"] + max_shares
                        validated[symbol]["reason"] = "Scaled down due to cash"
                    
                    total_available = 0
                else:
                    total_available -= cost
                
                # Check position limit
                if max_position_value and trade["target_value"] > max_position_value:
                    max_shares = max_position_value / trade["price"]
                    if not self.allow_fractional:
                        max_shares = int(max_shares)
                    
                    delta = max_shares - trade["current_shares"]
                    if delta <= 0:
                        validated[symbol]["action"] = "HOLD"
                        validated[symbol]["shares_to_trade"] = 0
                        validated[symbol]["trade_value"] = 0
                    else:
                        validated[symbol]["shares_to_trade"] = delta
                        validated[symbol]["trade_value"] = delta * trade["price"]
                        validated[symbol]["target_shares"] = max_shares
                    validated[symbol]["reason"] = "Position limit applied"
        
        return validated
