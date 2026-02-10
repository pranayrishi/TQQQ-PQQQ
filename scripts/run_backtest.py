#!/usr/bin/env python3
"""
Run Backtest Script

Runs backtests with the trading strategies and generates reports.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import pandas as pd

from src.data.data_manager import DataManager
from src.strategies.strategy_aggregator import StrategyAggregator
from src.backtest.backtest_engine import BacktestEngine
from src.visualization.equity_curve import plot_equity_curve, plot_drawdown_chart
from src.visualization.performance_report import generate_report


def main():
    parser = argparse.ArgumentParser(description="Run trading strategy backtest")
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Backtest start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Backtest end date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000,
        help="Initial capital for backtest"
    )
    parser.add_argument(
        "--output-dir",
        default="data/backtest_results",
        help="Directory for output files"
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip generating plots"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Trading Strategy Backtest")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = Path(__file__).parent.parent / config_path
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Override initial capital
        config["initial_capital"] = args.initial_capital
        
        # Create output directory
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = Path(__file__).parent.parent / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize data manager
        logger.info("Loading market data...")
        data_config = config.get("data", {})
        data_config["cache_dir"] = str(Path(__file__).parent.parent / data_config.get("cache_dir", "data/cache"))
        data_manager = DataManager(data_config)
        data_manager.initialize()
        
        # Get data
        ndx_data = data_manager.get_data("NDX", args.start_date, args.end_date)
        tqqq_data = data_manager.get_data("TQQQ", args.start_date, args.end_date)
        sqqq_data = data_manager.get_data("SQQQ", args.start_date, args.end_date)
        
        logger.info(f"NDX data: {len(ndx_data)} rows ({ndx_data['date'].min()} to {ndx_data['date'].max()})")
        logger.info(f"TQQQ data: {len(tqqq_data)} rows")
        logger.info(f"SQQQ data: {len(sqqq_data)} rows")
        
        # Initialize strategy aggregator
        logger.info("Initializing strategies...")
        strategy_config = config.get("strategies", {})
        aggregator = StrategyAggregator(strategy_config)
        
        # Run backtest
        logger.info("Running backtest...")
        backtest_config = {
            "initial_capital": args.initial_capital,
            "commission_per_trade": config.get("execution", {}).get("commission_per_trade", 0),
            "slippage_bps": config.get("execution", {}).get("slippage_bps", 5)
        }
        engine = BacktestEngine(backtest_config)
        
        results = engine.run_backtest(
            ndx_data, tqqq_data, sqqq_data,
            aggregator,
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        # Print summary
        print("\n" + results["summary"])
        
        # Save equity curve
        equity_path = output_dir / f"equity_curve_{timestamp}.csv"
        results["equity_curve"].to_csv(equity_path, index=False)
        logger.info(f"Saved equity curve to {equity_path}")
        
        # Save trades
        if results["trades"]:
            trades_df = pd.DataFrame(results["trades"])
            trades_path = output_dir / f"trades_{timestamp}.csv"
            trades_df.to_csv(trades_path, index=False)
            logger.info(f"Saved {len(trades_df)} trades to {trades_path}")
        
        # Generate report
        report_html_path = output_dir / f"report_{timestamp}.html"
        generate_report(results, str(report_html_path), format="html")
        logger.info(f"Saved HTML report to {report_html_path}")
        
        report_txt_path = output_dir / f"report_{timestamp}.txt"
        generate_report(results, str(report_txt_path), format="text")
        
        # Generate plots
        if not args.no_plots:
            logger.info("Generating plots...")
            
            equity_plot_path = output_dir / f"equity_curve_{timestamp}.png"
            plot_equity_curve(
                results["equity_curve"],
                title=f"Strategy Equity Curve (${args.initial_capital:,.0f} initial)",
                output_path=str(equity_plot_path)
            )
            
            drawdown_plot_path = output_dir / f"drawdown_{timestamp}.png"
            plot_drawdown_chart(
                results["equity_curve"],
                title="Strategy Drawdown",
                output_path=str(drawdown_plot_path)
            )
            
            logger.info(f"Saved plots to {output_dir}")
        
        logger.info("=" * 60)
        logger.info("Backtest Complete")
        logger.info("=" * 60)
        
        # Return key metrics
        metrics = results["metrics"]
        print(f"\nKey Metrics:")
        print(f"  Total Return: {metrics.get('total_return', 0):.2%}")
        print(f"  CAGR: {metrics.get('cagr', 0):.2%}")
        print(f"  Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
        print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
