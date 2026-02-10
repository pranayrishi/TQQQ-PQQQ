"""
Performance Report Generator

Generates comprehensive HTML and text reports from backtest results.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)


def generate_report(
    backtest_results: Dict,
    output_path: Optional[str] = None,
    format: str = "html"
) -> str:
    """
    Generate a performance report from backtest results.
    
    Args:
        backtest_results: Results from BacktestEngine.run_backtest()
        output_path: Optional path to save report
        format: Output format ('html' or 'text')
        
    Returns:
        Report content as string
    """
    metrics = backtest_results.get("metrics", {})
    equity_curve = backtest_results.get("equity_curve", pd.DataFrame())
    initial_capital = backtest_results.get("initial_capital", 100000)
    
    if format == "html":
        report = _generate_html_report(metrics, equity_curve, initial_capital)
    else:
        report = _generate_text_report(metrics, equity_curve, initial_capital)
    
    if output_path:
        with open(output_path, "w") as f:
            f.write(report)
        logger.info(f"Report saved to {output_path}")
    
    return report


def _generate_html_report(metrics: Dict, equity_curve: pd.DataFrame, initial_capital: float) -> str:
    """Generate HTML format report."""
    
    final_value = metrics.get("final_value", initial_capital)
    total_return = metrics.get("total_return", 0)
    cagr = metrics.get("cagr", 0)
    max_dd = metrics.get("max_drawdown", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading Strategy Performance Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #2E86AB, #1a5276);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .metric-card h3 {{
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
        }}
        .metric-card .value {{
            font-size: 28px;
            font-weight: bold;
            color: #2E86AB;
        }}
        .metric-card .value.positive {{
            color: #27ae60;
        }}
        .metric-card .value.negative {{
            color: #e74c3c;
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .section h2 {{
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #2E86AB;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Trading Strategy Performance Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-card">
            <h3>Initial Capital</h3>
            <div class="value">${initial_capital:,.0f}</div>
        </div>
        <div class="metric-card">
            <h3>Final Value</h3>
            <div class="value">${final_value:,.0f}</div>
        </div>
        <div class="metric-card">
            <h3>Total Return</h3>
            <div class="value {'positive' if total_return > 0 else 'negative'}">{total_return:+.1%}</div>
        </div>
        <div class="metric-card">
            <h3>CAGR</h3>
            <div class="value {'positive' if cagr > 0 else 'negative'}">{cagr:+.1%}</div>
        </div>
        <div class="metric-card">
            <h3>Max Drawdown</h3>
            <div class="value negative">{max_dd:.1%}</div>
        </div>
        <div class="metric-card">
            <h3>Sharpe Ratio</h3>
            <div class="value">{sharpe:.2f}</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Risk Metrics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Volatility (Annualized)</td>
                <td>{metrics.get('volatility', 0):.1%}</td>
            </tr>
            <tr>
                <td>Sortino Ratio</td>
                <td>{metrics.get('sortino_ratio', 0):.2f}</td>
            </tr>
            <tr>
                <td>Calmar Ratio</td>
                <td>{metrics.get('calmar_ratio', 0):.2f}</td>
            </tr>
            <tr>
                <td>Max Drawdown Duration</td>
                <td>{metrics.get('max_drawdown_duration_days', 0)} days</td>
            </tr>
        </table>
    </div>
    
    <div class="section">
        <h2>Trade Statistics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Number of Trades</td>
                <td>{metrics.get('num_trades', 0)}</td>
            </tr>
            <tr>
                <td>Win Rate</td>
                <td>{metrics.get('win_rate', 0):.1%}</td>
            </tr>
            <tr>
                <td>Average Win</td>
                <td>{metrics.get('avg_win', 0):.2%}</td>
            </tr>
            <tr>
                <td>Average Loss</td>
                <td>{metrics.get('avg_loss', 0):.2%}</td>
            </tr>
            <tr>
                <td>Profit Factor</td>
                <td>{metrics.get('profit_factor', 0):.2f}</td>
            </tr>
        </table>
    </div>
    
    <div class="section">
        <h2>Periodic Returns</h2>
        <table>
            <tr>
                <th>Period</th>
                <th>Best</th>
                <th>Worst</th>
                <th>Positive</th>
                <th>Negative</th>
            </tr>
            <tr>
                <td>Monthly</td>
                <td class="positive">{metrics.get('best_month', 0):+.1%}</td>
                <td class="negative">{metrics.get('worst_month', 0):+.1%}</td>
                <td>{metrics.get('positive_months', 0)}</td>
                <td>{metrics.get('negative_months', 0)}</td>
            </tr>
            <tr>
                <td>Yearly</td>
                <td class="positive">{metrics.get('best_year', 0):+.1%}</td>
                <td class="negative">{metrics.get('worst_year', 0):+.1%}</td>
                <td>{metrics.get('positive_years', 0)}</td>
                <td>{metrics.get('negative_years', 0)}</td>
            </tr>
        </table>
    </div>
    
    <div class="footer">
        <p>Automated Trading System - Performance Report</p>
    </div>
</body>
</html>
"""
    return html


def _generate_text_report(metrics: Dict, equity_curve: pd.DataFrame, initial_capital: float) -> str:
    """Generate plain text format report."""
    
    report = f"""
================================================================================
                    TRADING STRATEGY PERFORMANCE REPORT
================================================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY
--------------------------------------------------------------------------------
Initial Capital:     ${initial_capital:>15,.2f}
Final Value:         ${metrics.get('final_value', 0):>15,.2f}
Total Return:        {metrics.get('total_return', 0):>15.2%}
CAGR:                {metrics.get('cagr', 0):>15.2%}
Period:              {metrics.get('years', 0):>15.1f} years

RISK METRICS
--------------------------------------------------------------------------------
Max Drawdown:        {metrics.get('max_drawdown', 0):>15.2%}
Volatility:          {metrics.get('volatility', 0):>15.2%}
Sharpe Ratio:        {metrics.get('sharpe_ratio', 0):>15.2f}
Sortino Ratio:       {metrics.get('sortino_ratio', 0):>15.2f}
Calmar Ratio:        {metrics.get('calmar_ratio', 0):>15.2f}
Max DD Duration:     {metrics.get('max_drawdown_duration_days', 0):>15} days

TRADE STATISTICS
--------------------------------------------------------------------------------
Number of Trades:    {metrics.get('num_trades', 0):>15}
Win Rate:            {metrics.get('win_rate', 0):>15.2%}
Average Win:         {metrics.get('avg_win', 0):>15.2%}
Average Loss:        {metrics.get('avg_loss', 0):>15.2%}
Profit Factor:       {metrics.get('profit_factor', 0):>15.2f}

PERIODIC RETURNS
--------------------------------------------------------------------------------
Best Month:          {metrics.get('best_month', 0):>15.2%}
Worst Month:         {metrics.get('worst_month', 0):>15.2%}
Positive Months:     {metrics.get('positive_months', 0):>15}
Negative Months:     {metrics.get('negative_months', 0):>15}

Best Year:           {metrics.get('best_year', 0):>15.2%}
Worst Year:          {metrics.get('worst_year', 0):>15.2%}
Positive Years:      {metrics.get('positive_years', 0):>15}
Negative Years:      {metrics.get('negative_years', 0):>15}

================================================================================
"""
    return report
