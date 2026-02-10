"""
Main Entry Point

Launches the automated trading system with scheduling.
"""

import os
import sys
import logging
import signal
import argparse
from pathlib import Path
from typing import Dict
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scheduler import TradingScheduler


def setup_logging(log_level: str = "INFO", log_file: str = None) -> None:
    """Configure logging for the application."""
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Load credentials if they exist
    credentials_path = os.path.join(os.path.dirname(config_path), "credentials.yaml")
    if os.path.exists(credentials_path):
        with open(credentials_path, "r") as f:
            credentials = yaml.safe_load(f)
        
        # Merge credentials into config
        if credentials:
            # Data section
            if "polygon_api_key" in credentials:
                config.setdefault("data", {})["polygon_api_key"] = credentials["polygon_api_key"]
            
            # Broker section
            if "alpaca_api_key" in credentials:
                config.setdefault("brokers", {}).setdefault("alpaca", {})["api_key"] = credentials["alpaca_api_key"]
            if "alpaca_api_secret" in credentials:
                config.setdefault("brokers", {}).setdefault("alpaca", {})["api_secret"] = credentials["alpaca_api_secret"]
            
            # Alerts section
            if "twilio_account_sid" in credentials:
                config.setdefault("alerts", {}).setdefault("sms", {})["account_sid"] = credentials["twilio_account_sid"]
            if "twilio_auth_token" in credentials:
                config.setdefault("alerts", {}).setdefault("sms", {})["auth_token"] = credentials["twilio_auth_token"]
            if "email_username" in credentials:
                config.setdefault("alerts", {}).setdefault("email", {})["username"] = credentials["email_username"]
            if "email_password" in credentials:
                config.setdefault("alerts", {}).setdefault("email", {})["password"] = credentials["email_password"]
    
    # Override with environment variables
    env_mappings = {
        "POLYGON_API_KEY": ("data", "polygon_api_key"),
        "ALPACA_API_KEY": ("brokers", "alpaca", "api_key"),
        "ALPACA_API_SECRET": ("brokers", "alpaca", "api_secret"),
        "TWILIO_ACCOUNT_SID": ("alerts", "sms", "account_sid"),
        "TWILIO_AUTH_TOKEN": ("alerts", "sms", "auth_token"),
    }
    
    for env_var, path in env_mappings.items():
        value = os.environ.get(env_var)
        if value:
            current = config
            for key in path[:-1]:
                current = current.setdefault(key, {})
            current[path[-1]] = value
    
    return config


def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(description="Automated Trading System")
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--log-file",
        default="logs/trading.log",
        help="Path to log file"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run execution once and exit"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without executing trades"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Automated Trading System Starting")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = Path(__file__).parent.parent / config_path
        
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(str(config_path))
        
        # Apply dry-run mode
        if args.dry_run:
            logger.info("DRY RUN MODE - No trades will be executed")
            config.setdefault("execution", {})["dry_run"] = True
        
        # Initialize scheduler
        scheduler = TradingScheduler(config)
        
        if args.run_once:
            # Single execution mode
            logger.info("Running single execution...")
            results = scheduler.run_now(force=True)
            logger.info(f"Execution completed: {results['status']}")
            
            if results.get("error"):
                logger.error(f"Error: {results['error']}")
                sys.exit(1)
        else:
            # Scheduled mode
            logger.info("Starting scheduler...")
            scheduler.start()
            
            # Handle shutdown signals
            def signal_handler(signum, frame):
                logger.info("Shutdown signal received")
                scheduler.stop()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Keep running
            logger.info("Scheduler running. Press Ctrl+C to stop.")
            
            import time
            while scheduler.is_running:
                time.sleep(1)
    
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
