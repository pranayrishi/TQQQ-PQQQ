"""
Equity Curve Visualization

Generates publication-quality equity curve charts
and drawdown visualizations.
"""

import logging
from typing import Dict, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib not installed, visualization disabled")


def plot_equity_curve(
    equity_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
    title: str = "Strategy Equity Curve",
    output_path: Optional[str] = None,
    figsize: tuple = (14, 7)
):
    """
    Plot equity curve with optional benchmark.
    
    Args:
        equity_df: DataFrame with 'date' and 'total_value' columns
        benchmark_df: Optional benchmark DataFrame with same columns
        title: Chart title
        output_path: If provided, save chart to this path
        figsize: Figure size tuple
        
    Returns:
        Matplotlib Figure object or None if matplotlib not available
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Cannot plot - matplotlib not installed")
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Convert dates
    dates = pd.to_datetime(equity_df["date"])
    
    # Plot strategy equity
    ax.plot(dates, equity_df["total_value"], 
            label="Strategy", color="#2E86AB", linewidth=2)
    
    # Plot benchmark if provided
    if benchmark_df is not None:
        bench_dates = pd.to_datetime(benchmark_df["date"])
        ax.plot(bench_dates, benchmark_df["total_value"],
                label="Buy & Hold", color="#E94F37", 
                linewidth=1.5, alpha=0.7)
    
    # Formatting
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Portfolio Value ($)", fontsize=12)
    
    # Y-axis formatting
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    
    # X-axis formatting
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    
    # Grid
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved equity curve to {output_path}")
    
    return fig


def plot_drawdown_chart(
    equity_df: pd.DataFrame,
    title: str = "Drawdown Analysis",
    output_path: Optional[str] = None,
    figsize: tuple = (14, 5)
):
    """
    Plot drawdown visualization.
    
    Shows drawdown depth over time with shading.
    
    Args:
        equity_df: DataFrame with 'date' and 'total_value' columns
        title: Chart title
        output_path: If provided, save chart to this path
        figsize: Figure size tuple
        
    Returns:
        Matplotlib Figure object or None
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Cannot plot - matplotlib not installed")
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Calculate drawdown
    equity = equity_df["total_value"].values
    dates = pd.to_datetime(equity_df["date"])
    
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak * 100  # As percentage
    
    # Plot
    ax.fill_between(dates, drawdown, 0, color="#E94F37", alpha=0.5)
    ax.plot(dates, drawdown, color="#E94F37", linewidth=1)
    
    # Formatting
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Drawdown (%)", fontsize=12)
    
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="black", linewidth=0.5)
    
    # Set y limits
    min_dd = drawdown.min()
    ax.set_ylim(min_dd * 1.1, 5)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved drawdown chart to {output_path}")
    
    return fig


def plot_monthly_returns_heatmap(
    equity_df: pd.DataFrame,
    title: str = "Monthly Returns (%)",
    output_path: Optional[str] = None,
    figsize: tuple = (14, 8)
):
    """
    Plot monthly returns as a heatmap.
    
    Args:
        equity_df: DataFrame with 'date' and 'total_value' columns
        title: Chart title
        output_path: If provided, save chart to this path
        figsize: Figure size tuple
        
    Returns:
        Matplotlib Figure object or None
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Cannot plot - matplotlib not installed")
        return None
    
    # Calculate monthly returns
    df = equity_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    
    monthly = df["total_value"].resample("ME").last()
    monthly_returns = monthly.pct_change() * 100
    
    # Create pivot table
    monthly_df = monthly_returns.reset_index()
    monthly_df["year"] = monthly_df["date"].dt.year
    monthly_df["month"] = monthly_df["date"].dt.month
    monthly_df = monthly_df.rename(columns={"total_value": "return"})
    
    pivot = monthly_df.pivot(index="year", columns="month", values="return")
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create heatmap
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto", vmin=-20, vmax=20)
    
    # Labels
    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    
    # Add value annotations
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.iloc[i, j]
            if not np.isnan(val):
                color = "white" if abs(val) > 10 else "black"
                ax.text(j, i, f"{val:.1f}", ha="center", va="center", 
                       color=color, fontsize=8)
    
    ax.set_title(title, fontsize=16, fontweight="bold")
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Return (%)")
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved monthly returns heatmap to {output_path}")
    
    return fig


def plot_position_history(
    equity_df: pd.DataFrame,
    title: str = "Position History",
    output_path: Optional[str] = None,
    figsize: tuple = (14, 4)
):
    """
    Plot position history over time.
    
    Args:
        equity_df: DataFrame with 'date' and 'position' columns
        title: Chart title
        output_path: If provided, save chart to this path
        figsize: Figure size tuple
        
    Returns:
        Matplotlib Figure object or None
    """
    if not HAS_MATPLOTLIB:
        return None
    
    if "position" not in equity_df.columns:
        logger.warning("No position column in equity DataFrame")
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    
    dates = pd.to_datetime(equity_df["date"])
    positions = equity_df["position"].map({"TQQQ": 1, "SQQQ": -1, "CASH": 0}).fillna(0)
    
    # Color by position
    colors = positions.map({1: "#2E86AB", -1: "#E94F37", 0: "#808080"})
    
    ax.fill_between(dates, positions, 0, alpha=0.5, 
                    color="#2E86AB", where=positions > 0, label="Long (TQQQ)")
    ax.fill_between(dates, positions, 0, alpha=0.5,
                    color="#E94F37", where=positions < 0, label="Short (SQQQ)")
    
    ax.set_title(title, fontsize=16, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Position", fontsize=12)
    ax.set_yticks([-1, 0, 1])
    ax.set_yticklabels(["Short", "Cash", "Long"])
    
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
    
    return fig
