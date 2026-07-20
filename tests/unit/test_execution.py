"""Unit tests for live-execution safety controls."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.execution.execution_engine import ExecutionEngine


def test_dry_run_does_not_submit_orders():
    engine = ExecutionEngine({"execution": {"dry_run": True}})
    engine.order_manager = MagicMock()
    engine.order_manager.get_portfolio_value.return_value = 100_000
    engine.order_manager.get_positions.return_value = {}
    engine.order_manager.get_cash_balance.return_value = 100_000
    engine.position_calculator.calculate_required_trades = MagicMock(
        return_value={
            "TQQQ": {
                "action": "BUY",
                "shares_to_trade": 10,
            }
        }
    )
    engine.position_calculator.validate_trades = MagicMock(
        return_value={
            "TQQQ": {
                "action": "BUY",
                "shares_to_trade": 10,
            }
        }
    )

    result = engine._execute_for_account(
        "test-account",
        {"TQQQ": 1.0},
        {"TQQQ": 100.0},
    )

    engine.order_manager.place_order.assert_not_called()
    assert result["status"] == "completed"
    assert result["executed_orders"][0]["status"] == "dry_run"


def test_live_execution_rejects_stale_market_data():
    engine = ExecutionEngine({})
    expected_date = engine.market_calendar.get_previous_trading_day(
        datetime.now(engine.timezone).date()
    )
    stale_date = (expected_date - timedelta(days=1)).strftime("%Y-%m-%d")
    engine.data_manager.get_latest_bar = MagicMock(
        return_value={"date": stale_date}
    )

    with pytest.raises(RuntimeError, match="market data is stale"):
        engine._assert_data_is_fresh()
