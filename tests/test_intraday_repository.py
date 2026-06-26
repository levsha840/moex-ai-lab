from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from core.db.intraday_repository import IntradayCandle, IntradayRepository


def test_intraday_candle_defaults():
    candle = IntradayCandle(
        ticker="sber",
        time=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        timeframe="1m",
        open=100,
        high=101,
        low=99,
        close=100.5,
        volume=1000,
    )

    assert candle.ticker == "sber"
    assert candle.source == "MOEX"


@patch("core.db.intraday_repository.execute_values")
@patch("core.db.intraday_repository.get_connection")
def test_upsert_many_returns_inserted_count(mock_get_connection, mock_execute_values):
    conn = MagicMock()
    cur = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = conn
    conn.cursor.return_value.__enter__.return_value = cur

    repo = IntradayRepository()
    count = repo.upsert_many([
        IntradayCandle(
            ticker="sber",
            time=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
            timeframe="1m",
            open=100,
            high=101,
            low=99,
            close=100.5,
            volume=1000,
        )
    ])

    assert count == 1
    assert mock_execute_values.called
    conn.commit.assert_called_once()


def test_upsert_many_empty_returns_zero():
    repo = IntradayRepository()
    assert repo.upsert_many([]) == 0


@patch("core.db.intraday_repository.get_connection")
def test_get_latest_zero_limit_returns_empty_without_db(mock_get_connection):
    repo = IntradayRepository()
    assert repo.get_latest("SBER", limit=0) == []
    mock_get_connection.assert_not_called()
