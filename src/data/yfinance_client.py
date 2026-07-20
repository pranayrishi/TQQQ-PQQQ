"""Yahoo Finance client for adjusted daily market data."""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooFinanceError(Exception):
    """Raised when Yahoo Finance data cannot be downloaded or normalized."""


class YahooFinanceClient:
    """Download split-adjusted daily OHLCV bars through yfinance."""

    SYMBOLS: Dict[str, str] = {
        "NDX": "^NDX",
        "TQQQ": "TQQQ",
        "SQQQ": "SQQQ",
    }
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def get_daily_bars(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Return adjusted daily OHLCV bars for an inclusive date range."""
        if ticker not in self.SYMBOLS:
            raise ValueError(f"Unsupported Yahoo Finance ticker: {ticker}")
        if start_date > end_date:
            return self._empty_frame()

        yahoo_symbol = self.SYMBOLS[ticker]
        exclusive_end = (
            datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                raw = yf.download(
                    yahoo_symbol,
                    start=start_date,
                    end=exclusive_end,
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                    repair=True,
                    progress=False,
                    threads=False,
                    ignore_tz=True,
                    multi_level_index=False,
                    timeout=30,
                )
                return self._normalize(raw, ticker, start_date, end_date)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Yahoo Finance download attempt %s failed for %s: %s",
                    attempt + 1,
                    ticker,
                    exc,
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))

        raise YahooFinanceError(
            f"Failed to download Yahoo Finance data for {ticker}"
        ) from last_error

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        return pd.DataFrame(
            columns=["date", "open", "high", "low", "close", "volume"]
        )

    @classmethod
    def _normalize(
        cls,
        raw: pd.DataFrame,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        if raw is None or raw.empty:
            logger.warning(
                "No Yahoo Finance data returned for %s from %s to %s",
                ticker,
                start_date,
                end_date,
            )
            return cls._empty_frame()

        data = raw.copy()
        if isinstance(data.columns, pd.MultiIndex):
            yahoo_symbol = cls.SYMBOLS[ticker]
            if yahoo_symbol in data.columns.get_level_values(-1):
                data = data.xs(yahoo_symbol, axis=1, level=-1)
            else:
                data.columns = data.columns.get_level_values(0)

        data = data.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        required = ["open", "high", "low", "close"]
        missing = [column for column in required if column not in data.columns]
        if missing:
            raise YahooFinanceError(
                f"Yahoo Finance response for {ticker} is missing: {', '.join(missing)}"
            )

        data = data.reset_index()
        index_column = data.columns[0]
        data["date"] = pd.to_datetime(data[index_column]).dt.strftime("%Y-%m-%d")
        data = data[(data["date"] >= start_date) & (data["date"] <= end_date)]

        if "volume" not in data.columns:
            data["volume"] = 0
        data["volume"] = data["volume"].fillna(0).astype(float).astype(int)
        for column in required:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        data = data.dropna(subset=required)
        data = data.drop_duplicates(subset=["date"], keep="last")
        data = data.sort_values("date").reset_index(drop=True)
        return data[["date", "open", "high", "low", "close", "volume"]]
