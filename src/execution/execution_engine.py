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
from ..brokers.alpaca_broker import AlpacaBroker
from ..data.data_manager import DataManager
from ..strategies.strategy_aggregator import StrategyAggregator
from ..utils.market_calendar import MarketCalendar

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
        self.market_calendar = MarketCalendar()

        alpaca_config = config.get("brokers", {}).get("alpaca", {})
        if alpaca_config.get("api_key") and alpaca_config.get("api_secret"):
            self.order_manager.register_broker(
                "alpaca",
                AlpacaBroker(alpaca_config),
            )
        else:
            logger.warning("Alpaca credentials are not configured")
        
        # State
        self._initialized = False
        self._last_execution: Optional[Dict] = None
        self._paper_mode = config.get("brokers", {}).get("alpaca", {}).get("paper", True)
        self._dry_run = config.get("execution", {}).get("dry_run", False)
    
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

        if not self._dry_run:
            if not connection_results:
                raise RuntimeError("No broker is configured for live execution")
            if not all(connection_results.values()):
                raise RuntimeError("A configured broker failed to connect")
        
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
            "dry_run": self._dry_run,
            "status": "pending"
        }
        
        try:
            # Check if within execution window
            if not force and not self._is_execution_window():
                result["status"] = "skipped"
                result["reason"] = "Outside execution window"
                logger.info("Outside execution window, skipping")
                return result

            try:
                result["market_clock"] = self.order_manager.get_market_clock()
                if (
                    not self._dry_run
                    and not result["market_clock"].get("is_open", False)
                ):
                    result["status"] = "skipped"
                    result["reason"] = "Alpaca reports that the market is closed"
                    logger.warning("Alpaca market clock is closed; skipping")
                    return result
            except Exception:
                if not self._dry_run:
                    raise
                logger.warning("Could not retrieve Alpaca market clock in dry run")
            
            # Refresh data
            logger.info("Refreshing market data...")
            self.data_manager.refresh_intraday()

            if not self._dry_run:
                self._assert_data_is_fresh()
            
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

            # Use Alpaca's consolidated snapshots for live order sizing.
            result["market_data"] = {}
            try:
                snapshots = self.order_manager.get_market_snapshots(
                    ["TQQQ", "SQQQ"]
                )
                for symbol in ("TQQQ", "SQQQ"):
                    snapshot = snapshots.get(symbol, {})
                    quote = snapshot.get("latest_quote", {})
                    trade = snapshot.get("latest_trade", {})
                    minute_bar = snapshot.get("minute_bar", {})
                    daily_bar = snapshot.get("daily_bar", {})

                    bid = quote.get("bid", 0)
                    ask = quote.get("ask", 0)
                    candidates = [
                        ("quote_midpoint", (bid + ask) / 2 if bid and ask else 0),
                        ("latest_trade", trade.get("price", 0)),
                        ("minute_bar", minute_bar.get("close", 0)),
                        ("daily_bar", daily_bar.get("close", 0)),
                    ]
                    for source, price in candidates:
                        if price and price > 0:
                            current_prices[symbol] = price
                            result["market_data"][symbol] = {
                                "price_source": source,
                                "snapshot": snapshot,
                            }
                            break
            except Exception as exc:
                logger.warning(
                    "Could not get Alpaca snapshots; using yfinance closes: %s",
                    exc,
                )
            
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

                    if self._dry_run:
                        result["executed_orders"].append({
                            "symbol": symbol,
                            "side": trade["action"],
                            "qty": abs(shares),
                            "status": "dry_run",
                        })
                        logger.info(
                            "Dry run: would place %s order for %.2f %s",
                            trade["action"],
                            abs(shares),
                            symbol,
                        )
                        continue
                    
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

    def _assert_data_is_fresh(self) -> None:
        """Stop live execution unless all datasets include the prior session."""
        today = datetime.now(self.timezone).date()
        expected_date = self.market_calendar.get_previous_trading_day(today)
        stale = []

        for ticker in ("NDX", "TQQQ", "SQQQ"):
            latest_date = datetime.strptime(
                self.data_manager.get_latest_bar(ticker)["date"],
                "%Y-%m-%d",
            ).date()
            if latest_date < expected_date:
                stale.append(f"{ticker} latest={latest_date}")

        if stale:
            raise RuntimeError(
                "Live execution blocked because market data is stale; expected at "
                f"least {expected_date}: {', '.join(stale)}"
            )
    
    def get_status(self) -> Dict:
        """Get current engine status."""
        return {
            "initialized": self._initialized,
            "paper_mode": self._paper_mode,
            "dry_run": self._dry_run,
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
