"""
Backtest Engine

Simulates trading strategy performance on historical data.
Handles position transitions, slippage, and generates equity curves.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

from .performance_metrics import PerformanceMetrics
from ..strategies.strategy_aggregator import StrategyAggregator

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Backtesting engine for strategy evaluation.
    
    Features:
    - Event-driven simulation
    - Realistic execution modeling
    - Comprehensive performance tracking
    - Support for leveraged ETFs
    """
    
    def __init__(self, config: Dict):
        """
        Initialize backtest engine.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.initial_capital = config.get("initial_capital", 100000)
        self.commission = config.get("commission_per_trade", 0.0)
        self.slippage_bps = config.get("slippage_bps", 5)  # 5 basis points default
        
        # State
        self._reset_state()
    
    def _reset_state(self) -> None:
        """Reset backtest state."""
        self.cash = self.initial_capital
        self.positions = {"TQQQ": 0, "SQQQ": 0}
        self.equity_history: List[Dict] = []
        self.trade_history: List[Dict] = []
        self.current_position = "CASH"
    
    def run_backtest(
        self,
        ndx_data: pd.DataFrame,
        tqqq_data: pd.DataFrame,
        sqqq_data: pd.DataFrame,
        aggregator: StrategyAggregator,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        Run backtest simulation.
        
        Args:
            ndx_data: NDX index data for signal generation
            tqqq_data: TQQQ price data
            sqqq_data: SQQQ price data
            aggregator: Strategy aggregator for generating signals
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary with equity curve and metrics
        """
        self._reset_state()
        aggregator.reset_state()
        
        # Align data by date
        ndx_data = ndx_data.copy()
        tqqq_data = tqqq_data.copy()
        sqqq_data = sqqq_data.copy()
        
        # Apply date filters
        if start_date:
            ndx_data = ndx_data[ndx_data["date"] >= start_date]
            tqqq_data = tqqq_data[tqqq_data["date"] >= start_date]
            sqqq_data = sqqq_data[sqqq_data["date"] >= start_date]
        
        if end_date:
            ndx_data = ndx_data[ndx_data["date"] <= end_date]
            tqqq_data = tqqq_data[tqqq_data["date"] <= end_date]
            sqqq_data = sqqq_data[sqqq_data["date"] <= end_date]
        
        # Create date index for alignment
        tqqq_prices = tqqq_data.set_index("date")["close"].to_dict()
        sqqq_prices = sqqq_data.set_index("date")["close"].to_dict()
        
        # Get common dates (where we have both ETF prices)
        common_dates = set(tqqq_prices.keys()) & set(sqqq_prices.keys())
        
        logger.info(f"Running backtest from {min(common_dates)} to {max(common_dates)}")
        logger.info(f"Total trading days: {len(common_dates)}")
        
        # Simulate day by day
        for i in range(len(ndx_data)):
            current_date = ndx_data.iloc[i]["date"]
            
            # Skip if we don't have ETF prices for this date
            if current_date not in common_dates:
                continue
            
            tqqq_price = tqqq_prices[current_date]
            sqqq_price = sqqq_prices[current_date]
            
            # Get historical data up to current date for signal generation
            historical_data = ndx_data.iloc[:i+1].copy()
            
            # Generate signals
            tqqq_target, sqqq_target = aggregator.generate_signals(historical_data)
            
            # Calculate current portfolio value
            portfolio_value = self._calculate_portfolio_value(tqqq_price, sqqq_price)
            
            # Execute trades based on signals
            self._execute_trades(
                tqqq_target, sqqq_target,
                tqqq_price, sqqq_price,
                portfolio_value, current_date
            )
            
            # Record equity
            new_portfolio_value = self._calculate_portfolio_value(tqqq_price, sqqq_price)
            
            position_type = "CASH"
            if self.positions["TQQQ"] > 0:
                position_type = "TQQQ"
            elif self.positions["SQQQ"] > 0:
                position_type = "SQQQ"
            
            self.equity_history.append({
                "date": current_date,
                "total_value": new_portfolio_value,
                "cash": self.cash,
                "tqqq_shares": self.positions["TQQQ"],
                "sqqq_shares": self.positions["SQQQ"],
                "tqqq_value": self.positions["TQQQ"] * tqqq_price,
                "sqqq_value": self.positions["SQQQ"] * sqqq_price,
                "position": position_type,
                "tqqq_target": tqqq_target,
                "sqqq_target": sqqq_target
            })
        
        # Create equity curve DataFrame
        equity_curve = pd.DataFrame(self.equity_history)
        
        # Calculate performance metrics
        metrics = PerformanceMetrics(equity_curve, self.initial_capital)
        
        logger.info(f"Backtest complete. Final value: ${equity_curve['total_value'].iloc[-1]:,.2f}")
        
        return {
            "equity_curve": equity_curve,
            "metrics": metrics.get_metrics(),
            "summary": metrics.get_summary(),
            "trades": self.trade_history,
            "initial_capital": self.initial_capital
        }
    
    def _calculate_portfolio_value(self, tqqq_price: float, sqqq_price: float) -> float:
        """Calculate current portfolio value."""
        tqqq_value = self.positions["TQQQ"] * tqqq_price
        sqqq_value = self.positions["SQQQ"] * sqqq_price
        return self.cash + tqqq_value + sqqq_value
    
    def _execute_trades(
        self,
        tqqq_target: float,
        sqqq_target: float,
        tqqq_price: float,
        sqqq_price: float,
        portfolio_value: float,
        date: str
    ) -> None:
        """
        Execute trades to reach target positions.
        
        Args:
            tqqq_target: Target TQQQ allocation (0-1)
            sqqq_target: Target SQQQ allocation (0-1)
            tqqq_price: Current TQQQ price
            sqqq_price: Current SQQQ price
            portfolio_value: Current portfolio value
            date: Current date
        """
        # Calculate target values
        target_tqqq_value = portfolio_value * tqqq_target
        target_sqqq_value = portfolio_value * sqqq_target
        
        # Calculate target shares
        target_tqqq_shares = int(target_tqqq_value / tqqq_price) if tqqq_price > 0 else 0
        target_sqqq_shares = int(target_sqqq_value / sqqq_price) if sqqq_price > 0 else 0
        
        # Calculate required trades
        tqqq_delta = target_tqqq_shares - self.positions["TQQQ"]
        sqqq_delta = target_sqqq_shares - self.positions["SQQQ"]
        
        # Execute TQQQ trade
        if tqqq_delta != 0:
            self._execute_single_trade("TQQQ", tqqq_delta, tqqq_price, date)
        
        # Execute SQQQ trade
        if sqqq_delta != 0:
            self._execute_single_trade("SQQQ", sqqq_delta, sqqq_price, date)
    
    def _execute_single_trade(
        self,
        symbol: str,
        shares: int,
        price: float,
        date: str
    ) -> None:
        """
        Execute a single trade with slippage and commission.
        
        Args:
            symbol: Ticker symbol
            shares: Number of shares (positive=buy, negative=sell)
            price: Current price
            date: Trade date
        """
        if shares == 0:
            return
        
        # Apply slippage
        slippage = price * (self.slippage_bps / 10000)
        if shares > 0:  # Buying
            execution_price = price + slippage
        else:  # Selling
            execution_price = price - slippage
        
        # Calculate trade value
        trade_value = abs(shares) * execution_price
        
        # Apply commission
        total_cost = trade_value + self.commission
        
        if shares > 0:  # Buying
            if total_cost > self.cash:
                # Reduce shares to fit available cash
                shares = int((self.cash - self.commission) / execution_price)
                if shares <= 0:
                    return
                trade_value = shares * execution_price
                total_cost = trade_value + self.commission
            
            self.cash -= total_cost
            self.positions[symbol] += shares
        else:  # Selling
            shares_to_sell = min(abs(shares), self.positions[symbol])
            if shares_to_sell <= 0:
                return
            
            trade_value = shares_to_sell * execution_price
            self.cash += trade_value - self.commission
            self.positions[symbol] -= shares_to_sell
            shares = -shares_to_sell
        
        # Record trade
        self.trade_history.append({
            "date": date,
            "symbol": symbol,
            "shares": shares,
            "price": execution_price,
            "value": trade_value,
            "commission": self.commission,
            "action": "BUY" if shares > 0 else "SELL"
        })
    
    def run_walk_forward(
        self,
        ndx_data: pd.DataFrame,
        tqqq_data: pd.DataFrame,
        sqqq_data: pd.DataFrame,
        aggregator: StrategyAggregator,
        train_period_days: int = 756,  # ~3 years
        test_period_days: int = 252    # ~1 year
    ) -> List[Dict]:
        """
        Run walk-forward optimization/validation.
        
        Args:
            ndx_data: NDX data
            tqqq_data: TQQQ data
            sqqq_data: SQQQ data
            aggregator: Strategy aggregator
            train_period_days: Training period length
            test_period_days: Testing period length
            
        Returns:
            List of results for each walk-forward period
        """
        results = []
        
        # Get unique dates
        dates = sorted(set(ndx_data["date"]) & set(tqqq_data["date"]) & set(sqqq_data["date"]))
        
        start_idx = train_period_days
        
        while start_idx + test_period_days <= len(dates):
            test_start = dates[start_idx]
            test_end = dates[min(start_idx + test_period_days - 1, len(dates) - 1)]
            
            logger.info(f"Walk-forward period: {test_start} to {test_end}")
            
            # Run backtest for this period
            period_result = self.run_backtest(
                ndx_data, tqqq_data, sqqq_data,
                aggregator,
                start_date=test_start,
                end_date=test_end
            )
            
            period_result["period_start"] = test_start
            period_result["period_end"] = test_end
            results.append(period_result)
            
            # Move to next period
            start_idx += test_period_days
        
        return results
