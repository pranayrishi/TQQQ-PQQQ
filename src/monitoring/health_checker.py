"""
Health Checker

Monitors system health and reports issues.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pytz

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    System health monitoring.
    
    Checks:
    - Data freshness
    - Broker connectivity
    - Strategy functionality
    - System resources
    """
    
    def __init__(self, config: Dict):
        """
        Initialize health checker.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.timezone = pytz.timezone(config.get("timezone", "US/Eastern"))
        self._last_check: Optional[Dict] = None
    
    def run_health_check(
        self,
        data_manager=None,
        order_manager=None,
        aggregator=None
    ) -> Dict:
        """
        Run comprehensive health check.
        
        Args:
            data_manager: DataManager instance
            order_manager: OrderManager instance
            aggregator: StrategyAggregator instance
            
        Returns:
            Health check results dictionary
        """
        results = {
            "timestamp": datetime.now(self.timezone).isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        issues = []
        
        # Check data freshness
        if data_manager:
            data_check = self._check_data_freshness(data_manager)
            results["checks"]["data"] = data_check
            if data_check["status"] != "healthy":
                issues.append(f"Data: {data_check['message']}")
        
        # Check broker connectivity
        if order_manager:
            broker_check = self._check_broker_connectivity(order_manager)
            results["checks"]["brokers"] = broker_check
            if broker_check["status"] != "healthy":
                issues.append(f"Brokers: {broker_check['message']}")
        
        # Check strategy functionality
        if aggregator and data_manager:
            strategy_check = self._check_strategies(aggregator, data_manager)
            results["checks"]["strategies"] = strategy_check
            if strategy_check["status"] != "healthy":
                issues.append(f"Strategies: {strategy_check['message']}")
        
        # Determine overall status
        if issues:
            results["overall_status"] = "degraded" if len(issues) < 3 else "unhealthy"
            results["issues"] = issues
        
        self._last_check = results
        return results
    
    def _check_data_freshness(self, data_manager) -> Dict:
        """Check if data is up to date."""
        try:
            if not data_manager.is_initialized:
                return {
                    "status": "unhealthy",
                    "message": "Data manager not initialized"
                }
            
            # Check each ticker
            stale_tickers = []
            today = datetime.now(self.timezone).date()
            
            for ticker in ["NDX", "TQQQ", "SQQQ"]:
                try:
                    latest = data_manager.get_latest_bar(ticker)
                    latest_date = datetime.strptime(latest["date"], "%Y-%m-%d").date()
                    
                    # Data is stale if more than 3 days old (accounting for weekends)
                    days_old = (today - latest_date).days
                    if days_old > 3:
                        stale_tickers.append(f"{ticker} ({days_old} days old)")
                except Exception as e:
                    stale_tickers.append(f"{ticker} (error: {e})")
            
            if stale_tickers:
                return {
                    "status": "degraded",
                    "message": f"Stale data: {', '.join(stale_tickers)}"
                }
            
            return {
                "status": "healthy",
                "message": "All data is current"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Data check failed: {e}"
            }
    
    def _check_broker_connectivity(self, order_manager) -> Dict:
        """Check broker connections."""
        try:
            connected = []
            disconnected = []
            
            for name, broker in order_manager.brokers.items():
                if broker.is_connected:
                    connected.append(name)
                else:
                    disconnected.append(name)
            
            if not connected and disconnected:
                return {
                    "status": "unhealthy",
                    "message": f"No brokers connected. Disconnected: {', '.join(disconnected)}"
                }
            elif disconnected:
                return {
                    "status": "degraded",
                    "message": f"Some brokers disconnected: {', '.join(disconnected)}"
                }
            elif connected:
                return {
                    "status": "healthy",
                    "message": f"Connected: {', '.join(connected)}"
                }
            else:
                return {
                    "status": "degraded",
                    "message": "No brokers configured"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Broker check failed: {e}"
            }
    
    def _check_strategies(self, aggregator, data_manager) -> Dict:
        """Check if strategies can generate signals."""
        try:
            ndx_data = data_manager.get_data("NDX")
            
            if len(ndx_data) < 260:
                return {
                    "status": "degraded",
                    "message": f"Insufficient data for strategies ({len(ndx_data)} days)"
                }
            
            # Try generating signals
            tqqq, sqqq = aggregator.generate_signals(ndx_data)
            
            # Check if signals are valid
            if not (0 <= tqqq <= 1 and 0 <= sqqq <= 1):
                return {
                    "status": "unhealthy",
                    "message": f"Invalid signals: TQQQ={tqqq}, SQQQ={sqqq}"
                }
            
            return {
                "status": "healthy",
                "message": f"Signals generated: TQQQ={tqqq:.2%}, SQQQ={sqqq:.2%}"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Strategy check failed: {e}"
            }
    
    def get_last_check(self) -> Optional[Dict]:
        """Get results of last health check."""
        return self._last_check
    
    def get_status_summary(self) -> str:
        """Get a formatted status summary."""
        if not self._last_check:
            return "No health check performed yet"
        
        check = self._last_check
        
        summary = f"""
System Health Status
====================
Timestamp: {check['timestamp']}
Overall Status: {check['overall_status'].upper()}

"""
        
        for check_name, check_result in check.get("checks", {}).items():
            status_icon = "✓" if check_result["status"] == "healthy" else "⚠" if check_result["status"] == "degraded" else "✗"
            summary += f"{status_icon} {check_name.capitalize()}: {check_result['message']}\n"
        
        if check.get("issues"):
            summary += f"\nIssues:\n"
            for issue in check["issues"]:
                summary += f"  - {issue}\n"
        
        return summary
