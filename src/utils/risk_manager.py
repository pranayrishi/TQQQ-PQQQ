"""
Risk Management

Implements safety checks and circuit breakers.
"""

import logging
from datetime import datetime, date
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Risk management and safety checks.
    
    CRITICAL: This class implements safety mechanisms
    that should NEVER be bypassed.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize risk manager.
        
        Args:
            config: Risk configuration
        """
        self.config = config
        
        # Limits
        self.max_position_pct = config.get("max_position_pct", 1.0)
        self.max_daily_loss_pct = config.get("max_daily_loss_pct", 0.10)
        self.max_order_value = config.get("max_order_value", 1000000)
        self.min_cash_reserve = config.get("min_cash_reserve", 0)
        
        # State
        self._daily_start_value: Optional[float] = None
        self._trading_halted = False
        self._halt_reason: Optional[str] = None
        self._daily_trades = 0
        self._max_daily_trades = config.get("max_daily_trades", 10)
    
    def set_daily_start_value(self, value: float) -> None:
        """Record portfolio value at start of day."""
        self._daily_start_value = value
        self._daily_trades = 0
        logger.info(f"Daily start value: ${value:,.2f}")
    
    def check_position_limits(self, tqqq_pct: float, sqqq_pct: float) -> tuple:
        """
        Validate position percentages.
        
        Args:
            tqqq_pct: Target TQQQ percentage
            sqqq_pct: Target SQQQ percentage
            
        Returns:
            Validated (tqqq_pct, sqqq_pct) tuple
        """
        total = tqqq_pct + sqqq_pct
        
        if total > self.max_position_pct:
            # Scale down proportionally
            scale = self.max_position_pct / total
            tqqq_pct *= scale
            sqqq_pct *= scale
            logger.warning(f"Positions scaled down to {self.max_position_pct:.0%} limit")
        
        # Ensure within bounds
        tqqq_pct = max(0.0, min(1.0, tqqq_pct))
        sqqq_pct = max(0.0, min(1.0, sqqq_pct))
        
        return (tqqq_pct, sqqq_pct)
    
    def check_order_validity(self, order: Dict) -> tuple:
        """
        Validate an order before submission.
        
        Args:
            order: Order dictionary with 'shares', 'price', 'symbol'
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if self._trading_halted:
            return (False, f"Trading halted: {self._halt_reason}")
        
        # Check order value
        order_value = abs(order.get("shares", 0) * order.get("price", 0))
        if order_value > self.max_order_value:
            return (False, f"Order value ${order_value:,.2f} exceeds limit ${self.max_order_value:,.2f}")
        
        # Check daily trade count
        if self._daily_trades >= self._max_daily_trades:
            return (False, f"Daily trade limit ({self._max_daily_trades}) reached")
        
        # Check for reasonable share count
        shares = abs(order.get("shares", 0))
        if shares > 100000:
            return (False, f"Unusually large order: {shares} shares")
        
        # Check for reasonable price
        price = order.get("price", 0)
        if price <= 0:
            return (False, f"Invalid price: {price}")
        
        return (True, "Order valid")
    
    def check_daily_loss(self, current_value: float) -> tuple:
        """
        Check if daily loss limit exceeded.
        
        Args:
            current_value: Current portfolio value
            
        Returns:
            Tuple of (within_limits, loss_pct)
        """
        if self._daily_start_value is None:
            return (True, 0.0)
        
        loss_pct = (self._daily_start_value - current_value) / self._daily_start_value
        
        if loss_pct > self.max_daily_loss_pct:
            self.halt_trading(f"Daily loss {loss_pct:.1%} exceeds {self.max_daily_loss_pct:.1%} limit")
            return (False, loss_pct)
        
        return (True, loss_pct)
    
    def check_cash_reserve(self, cash: float, portfolio_value: float) -> tuple:
        """
        Check if minimum cash reserve is maintained.
        
        Args:
            cash: Available cash
            portfolio_value: Total portfolio value
            
        Returns:
            Tuple of (sufficient, message)
        """
        if self.min_cash_reserve <= 0:
            return (True, "No cash reserve required")
        
        if cash < self.min_cash_reserve:
            return (False, f"Cash ${cash:,.2f} below reserve ${self.min_cash_reserve:,.2f}")
        
        return (True, "Cash reserve adequate")
    
    def record_trade(self) -> None:
        """Record that a trade was executed."""
        self._daily_trades += 1
        logger.debug(f"Daily trades: {self._daily_trades}/{self._max_daily_trades}")
    
    def halt_trading(self, reason: str) -> None:
        """
        Halt all trading.
        
        Args:
            reason: Reason for halt
        """
        self._trading_halted = True
        self._halt_reason = reason
        logger.critical(f"TRADING HALTED: {reason}")
    
    def resume_trading(self) -> None:
        """Resume trading after halt."""
        self._trading_halted = False
        self._halt_reason = None
        logger.info("Trading resumed")
    
    @property
    def is_trading_halted(self) -> bool:
        """Check if trading is halted."""
        return self._trading_halted
    
    @property
    def halt_reason(self) -> Optional[str]:
        """Get the reason for trading halt."""
        return self._halt_reason
    
    def reset_daily_state(self) -> None:
        """Reset daily tracking state."""
        self._daily_start_value = None
        self._daily_trades = 0
        logger.info("Daily risk state reset")
    
    def get_status(self) -> Dict:
        """Get current risk manager status."""
        return {
            "trading_halted": self._trading_halted,
            "halt_reason": self._halt_reason,
            "daily_start_value": self._daily_start_value,
            "daily_trades": self._daily_trades,
            "max_daily_trades": self._max_daily_trades,
            "max_position_pct": self.max_position_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_order_value": self.max_order_value
        }
    
    def validate_strategy_output(self, tqqq_pct: float, sqqq_pct: float) -> tuple:
        """
        Validate strategy output before execution.
        
        Args:
            tqqq_pct: TQQQ allocation percentage
            sqqq_pct: SQQQ allocation percentage
            
        Returns:
            Tuple of (is_valid, validated_tqqq, validated_sqqq, warnings)
        """
        warnings = []
        
        # Check for NaN or infinity
        import math
        if math.isnan(tqqq_pct) or math.isinf(tqqq_pct):
            warnings.append("Invalid TQQQ percentage, setting to 0")
            tqqq_pct = 0.0
        
        if math.isnan(sqqq_pct) or math.isinf(sqqq_pct):
            warnings.append("Invalid SQQQ percentage, setting to 0")
            sqqq_pct = 0.0
        
        # Check for negative values
        if tqqq_pct < 0:
            warnings.append(f"Negative TQQQ {tqqq_pct:.2%}, clamping to 0")
            tqqq_pct = 0.0
        
        if sqqq_pct < 0:
            warnings.append(f"Negative SQQQ {sqqq_pct:.2%}, clamping to 0")
            sqqq_pct = 0.0
        
        # Check for both long and short (unusual)
        if tqqq_pct > 0.1 and sqqq_pct > 0.1:
            warnings.append(f"Both TQQQ and SQQQ non-zero: {tqqq_pct:.2%}, {sqqq_pct:.2%}")
        
        # Apply position limits
        tqqq_pct, sqqq_pct = self.check_position_limits(tqqq_pct, sqqq_pct)
        
        is_valid = len(warnings) == 0 or all("clamping" in w or "setting" in w for w in warnings)
        
        return (is_valid, tqqq_pct, sqqq_pct, warnings)
