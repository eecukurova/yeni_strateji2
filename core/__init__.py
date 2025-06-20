"""
Core package.

This package contains core classes
"""

from .trading_signal import TradingSignal
from .logging_config import LoggingConfig
__all__ = [
    'TradingSignal',
    'LoggingConfig',
    'telegram',

]
