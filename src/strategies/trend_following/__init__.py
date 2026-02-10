"""Trend following strategy modules."""

from .ma_breakout import MABreakoutLongStrategy, MABreakoutShortStrategy
from .momentum import MomentumLongStrategy, MomentumShortStrategy

__all__ = [
    "MABreakoutLongStrategy",
    "MABreakoutShortStrategy",
    "MomentumLongStrategy",
    "MomentumShortStrategy"
]
