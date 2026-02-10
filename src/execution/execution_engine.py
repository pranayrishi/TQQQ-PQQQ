"""
Execution Engine

Main execution logic for daily trading operations.
Coordinates data refresh, signal generation, and order execution.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
import pytz

from .position_calculator import PositionCalculator
from .order_manager import OrderManager
from ..data.data_manager import DataManager
from ..strategies.strategy_aggregator import StrategyAggregator

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Main execution engine for live trading.
    
    Coordinates:
    - Data refresh
    - Signal generation
    - Position calculation
    - Order execution
    - Status reporting
    """
    
    def __init__(self, config: Dict):
        """
        Initialize execution engine.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.timezone = pytz.timezone(config.get("timezone", "US/Eastern"))
        
        # Initialize components
        self.data_manager = DataManager(config.get("data", {}))
        self.aggregator = StrategyAggregator(config.get("strategies", {}))
        self.position_calculator = PositionCalculator(config.get("execution", {}))
        self.order_manager = OrderManager(config.get("brokers", {}))
        
        # State
        self._initialized = False
        self._last_execution: Optional[Dict] = None
        self._paper_mode = config.get("brokers", {}).get("alpaca", {}).get("paper", True)
    
    def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing execution engine...")
        
        # Initialize data
        self.data_manager.initialize()
        
        # Validate data
        for ticker in ["NDX", "TQQQ", "SQQQ"]:
            if not self.data_manager.validate_data(ticker):
                raise RuntimeError(f"Data validation failed for {ticker}")
        
        # Connect to brokers
        connection_results = self.order_manager.connect_all()
        
        for broker, success in connection_results.items():
            if not success:
                logger.warning(f"Failed to connect to {broker}")
        
        self._initialized = True
        logger.info("Execution engine initialized")
    
    def run(self, force: bool = False) -> Dict:
        """
        Run the execution workflow.
        
        Args:
            force: Force execution even outside trading window
            
        Returns:
            Execution result dictionary
        """
        if not self._initialized:
            self.initialize()
        
        execution_id = datetime.now(self.timezone).strftime("%Y%m%d_%H%M%S")
        logger.info(f"Starting execution {execution_id}")
        
        result = {
            "execution_id": execution_id,
            "timestamp": datetime.now(self.timezone).isoformat(),
            "paper_mode": self._paper_mode,
            "status": "pending"
        }
        
        try:
            # Check if within execution window
            if not force and not self._is_execution_window():
                result["status"] = "skipped"
                result["reason"] = "Outside execution window"
                logger.info("Outside execution window, skipping")
                return result
            
            # Refresh data
            logger.info("Refreshing market data...")
            self.data_manager.refresh_intraday()
            
            # Generate signals
            logger.info("Generating trading signals...")
            ndx_data = self.data_manager.get_data("NDX")
            tqqq_target, sqqq_target = self.aggregator.generate_signals(ndx_data)
            
            result["signals"] = {
                "tqqq_target": tqqq_target,
                "sqqq_target": sqqq_target
            }
            result["strategy_debug"] = self.aggregator.get_debug_info()
            
            logger.info(f"Target positions: TQQQ={tqqq_target:.2%}, SQQQ={sqqq_target:.2%}")
            
            # Get current prices
            tqqq_bar = self.data_manager.get_latest_bar("TQQQ")
            sqqq_bar = self.data_manager.get_latest_bar("SQQQ")
            
            current_prices = {
                "TQQQ": tqqq_bar["close"],
                "SQQQ": sqqq_bar["close"]
            }
            
            result["prices"] = current_prices
            
            # Execute for each account
            result["accounts"] = {}
            
            for account in self.order_manager.get_accounts():
                account_id = account["id"]
                account_result = self._execute_for_account(
                    account_id,
                    {"TQQQ": tqqq_target, "SQQQ": sqqq_target},
                    current_prices
                )
                result["accounts"][account_id] = account_result
            
            result["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            result["status"] = "error"
            result["error"] = str(e)
        
        self._last_execution = result
        return result
    
    def _execute_for_account(
        self,
        account_id: str,
        target_percentages: Dict[str, float],
        current_prices: Dict[str, float]
    ) -> Dict:
        """
        Execute trades for a single account.
        
        Args:
            account_id: Account identifier
            target_percentages: Target allocations
            current_prices: Current prices
            
        Returns:
            Account execution result
        """
        result = {
            "account_id": account_id,
            "status": "pending"
        }
        
        try:
            # Get current state
            portfolio_value = self.order_manager.get_portfolio_value(account_id)
            positions = self.order_manager.get_positions(account_id)
            cash = self.order_manager.get_cash_balance(account_id)
            
            # Convert positions to shares
            current_holdings = {}
            for symbol, pos in positions.items():
                current_holdings[symbol] = pos.get("shares", 0)
            
            result["portfolio_value"] = portfolio_value
            result["current_positions"] = positions
            result["cash"] = cash
            
            # Calculate required trades
            trades = self.position_calculator.calculate_required_trades(
                portfolio_value,
                current_holdings,
                target_percentages,
                current_prices
            )
            
            # Validate trades
            trades = self.position_calculator.validate_trades(
                trades,
                cash,
                portfolio_value  # Max position = full portfolio
            )
            
            result["calculated_trades"] = trades
            
            # Execute trades
            result["executed_orders"] = []
            
            for symbol, trade in trades.items():
                if trade["action"] in ["BUY", "SELL"]:
                    shares = trade["shares_to_trade"]
                    
                    try:
                        order_result = self.order_manager.place_order(
                            account_id=account_id,
                            symbol=symbol,
                            shares=shares,
                            order_type="market"
                        )
                        result["executed_orders"].append(order_result)
                        logger.info(f"Placed order: {trade['action']} {abs(shares):.2f} {symbol}")
                        
                    except Exception as e:
                        logger.error(f"Failed to place order for {symbol}: {e}")
                        result["executed_orders"].append({
                            "symbol": symbol,
                            "error": str(e),
                            "status": "failed"
                        })
            
            result["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Account execution failed: {e}")
            result["status"] = "error"
            result["error"] = str(e)
        
        return result
    
    def _is_execution_window(self) -> bool:
        """Check if current time is within execution window."""
        now = datetime.now(self.timezone)
        
        # Get execution window from config
        exec_config = self.config.get("execution", {})
        window_start = exec_config.get("execution_window_start", "15:50")
        window_end = exec_config.get("execution_window_end", "16:00")
        
        start_hour, start_min = map(int, window_start.split(":"))
        end_hour, end_min = map(int, window_end.split(":"))
        
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        return start_minutes <= current_minutes <= end_minutes
    
    def get_status(self) -> Dict:
        """Get current engine status."""
        return {
            "initialized": self._initialized,
            "paper_mode": self._paper_mode,
            "last_execution": self._last_execution,
            "data_loaded": self.data_manager.is_initialized if self._initialized else False,
            "connected_brokers": list(self.order_manager.brokers.keys()) if self._initialized else []
        }
    
    def close_all_positions(self, account_id: Optional[str] = None) -> Dict:
        """
        Emergency close all positions.
        
        Args:
            account_id: Specific account or all if None
            
        Returns:
            Results dictionary
        """
        results = {}
        
        accounts = [{"id": account_id}] if account_id else self.order_manager.get_accounts()
        
        for account in accounts:
            acc_id = account["id"]
            positions = self.order_manager.get_positions(acc_id)
            
            for symbol, pos in positions.items():
                shares = pos.get("shares", 0)
                if shares > 0:
                    try:
                        order = self.order_manager.place_order(
                            account_id=acc_id,
                            symbol=symbol,
                            shares=-shares,  # Negative to sell
                            order_type="market"
                        )
                        results[f"{acc_id}_{symbol}"] = order
                    except Exception as e:
                        results[f"{acc_id}_{symbol}"] = {"error": str(e)}
        
        return results
