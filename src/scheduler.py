"""
Scheduler

Manages automated execution scheduling.
The system runs only in the last 10 minutes of the trading day.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
import pytz

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    logger.warning("APScheduler not installed, scheduling disabled")

from .execution.execution_engine import ExecutionEngine
from .utils.market_calendar import MarketCalendar
from .monitoring.alert_manager import AlertManager
from .monitoring.health_checker import HealthChecker


class TradingScheduler:
    """
    Automated trading scheduler.
    
    Schedules execution for:
    - 3:50 PM ET on trading days (10 minutes before market close)
    - System health checks
    - Data refresh at market open
    """
    
    def __init__(self, config: Dict):
        """
        Initialize scheduler.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.timezone = pytz.timezone(config.get("system", {}).get("timezone", "US/Eastern"))
        
        # Initialize components
        self.execution_engine = ExecutionEngine(config)
        self.market_calendar = MarketCalendar()
        self.alert_manager = AlertManager(config.get("alerts", {}))
        self.health_checker = HealthChecker(config)
        
        # Scheduler
        if HAS_APSCHEDULER:
            self.scheduler = BackgroundScheduler(timezone=self.timezone)
        else:
            self.scheduler = None
        
        self._running = False
    
    def start(self) -> None:
        """Start the scheduler."""
        if not HAS_APSCHEDULER:
            logger.error("Cannot start scheduler - APScheduler not installed")
            return
        
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        # Initialize execution engine
        logger.info("Initializing execution engine...")
        self.execution_engine.initialize()
        
        # Schedule daily execution at 3:50 PM ET
        self.scheduler.add_job(
            self._daily_execution,
            CronTrigger(
                hour=15,
                minute=50,
                day_of_week="mon-fri",
                timezone=self.timezone
            ),
            id="daily_execution",
            name="Daily Trading Execution",
            replace_existing=True
        )
        
        # Schedule market open data refresh at 9:35 AM ET
        self.scheduler.add_job(
            self._market_open_check,
            CronTrigger(
                hour=9,
                minute=35,
                day_of_week="mon-fri",
                timezone=self.timezone
            ),
            id="market_open_check",
            name="Market Open Data Refresh",
            replace_existing=True
        )
        
        # Schedule health check every hour during market hours
        self.scheduler.add_job(
            self._health_check,
            CronTrigger(
                hour="9-16",
                minute=0,
                day_of_week="mon-fri",
                timezone=self.timezone
            ),
            id="health_check",
            name="Hourly Health Check",
            replace_existing=True
        )
        
        self.scheduler.start()
        self._running = True
        
        logger.info("Scheduler started")
        next_run = self.scheduler.get_job("daily_execution").next_run_time
        logger.info(f"Next execution scheduled: {next_run}")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        if self._running and self.scheduler:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Scheduler stopped")
    
    def _daily_execution(self) -> None:
        """Execute daily trading workflow."""
        today = datetime.now(self.timezone).date()
        
        # Check if market is open today
        if not self.market_calendar.is_trading_day(today):
            logger.info(f"{today} is not a trading day, skipping execution")
            return
        
        logger.info("Starting scheduled daily execution")
        
        try:
            results = self.execution_engine.run()
            
            # Only send email if actual trades were executed
            trades_made = False
            for account_id, account_data in results.get("accounts", {}).items():
                executed_orders = account_data.get("executed_orders", [])
                if executed_orders and len(executed_orders) > 0:
                    trades_made = True
                    break
            
            if trades_made:
                self.alert_manager.send_execution_summary(results)
                logger.info("Trade executed - email sent")
            else:
                logger.info("No trades needed - skipping email")
            
            logger.info(f"Execution completed: {results['status']}")
            
        except Exception as e:
            logger.error(f"Scheduled execution failed: {e}", exc_info=True)
            self.alert_manager.send_error_alert(str(e), {"context": "daily_execution"})
    
    def _market_open_check(self) -> None:
        """Refresh data at market open."""
        today = datetime.now(self.timezone).date()
        
        if not self.market_calendar.is_trading_day(today):
            return
        
        logger.info("Market open - refreshing data")
        
        try:
            self.execution_engine.data_manager.initialize()
            logger.info("Data refresh complete")
        except Exception as e:
            logger.error(f"Data refresh failed: {e}")
            self.alert_manager.send_error_alert(f"Data refresh failed: {e}")
    
    def _health_check(self) -> None:
        """Run system health check."""
        try:
            results = self.health_checker.run_health_check(
                data_manager=self.execution_engine.data_manager,
                order_manager=self.execution_engine.order_manager,
                aggregator=self.execution_engine.aggregator
            )
            
            if results["overall_status"] != "healthy":
                logger.warning(f"Health check: {results['overall_status']}")
                if results["overall_status"] == "unhealthy":
                    self.alert_manager.send_error_alert(
                        f"System unhealthy: {results.get('issues', [])}",
                        {"health_check": results}
                    )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def run_now(self, force: bool = True) -> Dict:
        """
        Manually trigger execution.
        
        Args:
            force: Force execution even outside trading window
            
        Returns:
            Execution results
        """
        if not self.execution_engine._initialized:
            self.execution_engine.initialize()
        
        return self.execution_engine.run(force=force)
    
    def get_status(self) -> Dict:
        """Get scheduler status."""
        status = {
            "running": self._running,
            "execution_engine": self.execution_engine.get_status()
        }
        
        if self._running and self.scheduler:
            jobs = []
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None
                })
            status["scheduled_jobs"] = jobs
        
        return status
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running
