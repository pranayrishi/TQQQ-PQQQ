"""
Performance Metrics

Calculates comprehensive trading performance metrics including:
- Total return, CAGR
- Maximum drawdown
- Sharpe ratio, Sortino ratio
- Win rate, profit factor
- Monthly and yearly returns
"""

import logging
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """
    Calculate and store performance metrics for a trading strategy.
    """
    
    RISK_FREE_RATE = 0.02  # 2% annual risk-free rate assumption
    TRADING_DAYS_PER_YEAR = 252
    
    def __init__(self, equity_curve: pd.DataFrame, initial_capital: float):
        """
        Initialize with equity curve data.
        
        Args:
            equity_curve: DataFrame with 'date' and 'total_value' columns
            initial_capital: Starting capital
        """
        self.equity_curve = equity_curve.copy()
        self.initial_capital = initial_capital
        self.metrics: Dict = {}
        
        self._calculate_all_metrics()
    
    def _calculate_all_metrics(self) -> None:
        """Calculate all performance metrics."""
        self._calculate_returns()
        self._calculate_drawdown()
        self._calculate_risk_metrics()
        self._calculate_trade_metrics()
        self._calculate_periodic_returns()
    
    def _calculate_returns(self) -> None:
        """Calculate return metrics."""
        if len(self.equity_curve) < 2:
            self.metrics["total_return"] = 0.0
            self.metrics["cagr"] = 0.0
            return
        
        final_value = self.equity_curve["total_value"].iloc[-1]
        
        # Total return
        total_return = (final_value - self.initial_capital) / self.initial_capital
        self.metrics["total_return"] = total_return
        
        # CAGR
        start_date = pd.to_datetime(self.equity_curve["date"].iloc[0])
        end_date = pd.to_datetime(self.equity_curve["date"].iloc[-1])
        years = (end_date - start_date).days / 365.25
        
        if years > 0 and final_value > 0:
            cagr = (final_value / self.initial_capital) ** (1 / years) - 1
        else:
            cagr = 0.0
        
        self.metrics["cagr"] = cagr
        self.metrics["years"] = years
        self.metrics["final_value"] = final_value
    
    def _calculate_drawdown(self) -> None:
        """Calculate drawdown metrics."""
        equity = self.equity_curve["total_value"].values
        
        # Running maximum
        peak = np.maximum.accumulate(equity)
        
        # Drawdown series
        drawdown = (equity - peak) / peak
        
        # Maximum drawdown
        max_drawdown = drawdown.min()
        self.metrics["max_drawdown"] = max_drawdown
        
        # Store drawdown series
        self.equity_curve["drawdown"] = drawdown
        
        # Calculate drawdown duration
        in_drawdown = drawdown < 0
        drawdown_periods = []
        current_start = None
        
        for i, (date, dd) in enumerate(zip(self.equity_curve["date"], in_drawdown)):
            if dd and current_start is None:
                current_start = i
            elif not dd and current_start is not None:
                drawdown_periods.append(i - current_start)
                current_start = None
        
        if current_start is not None:
            drawdown_periods.append(len(in_drawdown) - current_start)
        
        if drawdown_periods:
            self.metrics["max_drawdown_duration_days"] = max(drawdown_periods)
            self.metrics["avg_drawdown_duration_days"] = np.mean(drawdown_periods)
        else:
            self.metrics["max_drawdown_duration_days"] = 0
            self.metrics["avg_drawdown_duration_days"] = 0
    
    def _calculate_risk_metrics(self) -> None:
        """Calculate risk-adjusted return metrics."""
        # Daily returns
        self.equity_curve["daily_return"] = self.equity_curve["total_value"].pct_change()
        returns = self.equity_curve["daily_return"].dropna()
        
        if len(returns) < 2:
            self.metrics["sharpe_ratio"] = 0.0
            self.metrics["sortino_ratio"] = 0.0
            self.metrics["volatility"] = 0.0
            return
        
        # Annualized metrics
        mean_return = returns.mean() * self.TRADING_DAYS_PER_YEAR
        volatility = returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)
        
        self.metrics["volatility"] = volatility
        
        # Sharpe Ratio
        if volatility > 0:
            sharpe = (mean_return - self.RISK_FREE_RATE) / volatility
        else:
            sharpe = 0.0
        
        self.metrics["sharpe_ratio"] = sharpe
        
        # Sortino Ratio (downside volatility)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_volatility = downside_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)
            if downside_volatility > 0:
                sortino = (mean_return - self.RISK_FREE_RATE) / downside_volatility
            else:
                sortino = 0.0
        else:
            sortino = float('inf') if mean_return > self.RISK_FREE_RATE else 0.0
        
        self.metrics["sortino_ratio"] = sortino
        
        # Calmar Ratio
        if self.metrics["max_drawdown"] < 0:
            calmar = self.metrics["cagr"] / abs(self.metrics["max_drawdown"])
        else:
            calmar = float('inf') if self.metrics["cagr"] > 0 else 0.0
        
        self.metrics["calmar_ratio"] = calmar
    
    def _calculate_trade_metrics(self) -> None:
        """Calculate trade-level metrics."""
        if "position" not in self.equity_curve.columns:
            self.metrics["num_trades"] = 0
            self.metrics["win_rate"] = 0.0
            self.metrics["profit_factor"] = 0.0
            return
        
        # Identify trades (position changes)
        positions = self.equity_curve["position"].fillna("CASH")
        position_changes = positions != positions.shift(1)
        
        trades = []
        current_trade = None
        
        for i, (date, value, pos, changed) in enumerate(zip(
            self.equity_curve["date"],
            self.equity_curve["total_value"],
            positions,
            position_changes
        )):
            if changed:
                if current_trade is not None:
                    current_trade["exit_date"] = date
                    current_trade["exit_value"] = value
                    current_trade["return"] = (value - current_trade["entry_value"]) / current_trade["entry_value"]
                    trades.append(current_trade)
                
                if pos != "CASH":
                    current_trade = {
                        "entry_date": date,
                        "entry_value": value,
                        "position": pos
                    }
                else:
                    current_trade = None
        
        self.metrics["num_trades"] = len(trades)
        
        if trades:
            returns = [t["return"] for t in trades]
            winning_trades = [r for r in returns if r > 0]
            losing_trades = [r for r in returns if r <= 0]
            
            self.metrics["win_rate"] = len(winning_trades) / len(trades) if trades else 0.0
            self.metrics["avg_win"] = np.mean(winning_trades) if winning_trades else 0.0
            self.metrics["avg_loss"] = np.mean(losing_trades) if losing_trades else 0.0
            
            total_wins = sum(winning_trades) if winning_trades else 0.0
            total_losses = abs(sum(losing_trades)) if losing_trades else 0.0
            
            self.metrics["profit_factor"] = total_wins / total_losses if total_losses > 0 else float('inf')
        else:
            self.metrics["win_rate"] = 0.0
            self.metrics["avg_win"] = 0.0
            self.metrics["avg_loss"] = 0.0
            self.metrics["profit_factor"] = 0.0
    
    def _calculate_periodic_returns(self) -> None:
        """Calculate monthly and yearly returns."""
        df = self.equity_curve.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        
        # Monthly returns
        monthly = df["total_value"].resample("ME").last()
        monthly_returns = monthly.pct_change().dropna()
        
        self.metrics["monthly_returns"] = monthly_returns.to_dict()
        self.metrics["best_month"] = monthly_returns.max() if len(monthly_returns) > 0 else 0.0
        self.metrics["worst_month"] = monthly_returns.min() if len(monthly_returns) > 0 else 0.0
        self.metrics["positive_months"] = (monthly_returns > 0).sum()
        self.metrics["negative_months"] = (monthly_returns <= 0).sum()
        
        # Yearly returns
        yearly = df["total_value"].resample("YE").last()
        yearly_returns = yearly.pct_change().dropna()
        
        self.metrics["yearly_returns"] = yearly_returns.to_dict()
        self.metrics["best_year"] = yearly_returns.max() if len(yearly_returns) > 0 else 0.0
        self.metrics["worst_year"] = yearly_returns.min() if len(yearly_returns) > 0 else 0.0
        self.metrics["positive_years"] = (yearly_returns > 0).sum()
        self.metrics["negative_years"] = (yearly_returns <= 0).sum()
    
    def get_metrics(self) -> Dict:
        """Get all calculated metrics."""
        return self.metrics.copy()
    
    def get_summary(self) -> str:
        """Get a formatted summary string."""
        return f"""
Performance Summary
==================
Period: {self.metrics.get('years', 0):.1f} years
Final Value: ${self.metrics.get('final_value', 0):,.2f}

Returns
-------
Total Return: {self.metrics.get('total_return', 0):.2%}
CAGR: {self.metrics.get('cagr', 0):.2%}
Best Year: {self.metrics.get('best_year', 0):.2%}
Worst Year: {self.metrics.get('worst_year', 0):.2%}

Risk
----
Max Drawdown: {self.metrics.get('max_drawdown', 0):.2%}
Volatility: {self.metrics.get('volatility', 0):.2%}
Sharpe Ratio: {self.metrics.get('sharpe_ratio', 0):.2f}
Sortino Ratio: {self.metrics.get('sortino_ratio', 0):.2f}
Calmar Ratio: {self.metrics.get('calmar_ratio', 0):.2f}

Trades
------
Number of Trades: {self.metrics.get('num_trades', 0)}
Win Rate: {self.metrics.get('win_rate', 0):.2%}
Profit Factor: {self.metrics.get('profit_factor', 0):.2f}
"""
    
    def to_dataframe(self) -> pd.DataFrame:
        """Export metrics as a DataFrame."""
        # Filter out dict values
        simple_metrics = {k: v for k, v in self.metrics.items() 
                         if not isinstance(v, dict)}
        return pd.DataFrame([simple_metrics])
