from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

from psycopg2.extras import execute_values, RealDictCursor

from core.db.postgres import get_connection


@dataclass(frozen=True)
class IntradayCandle:
    ticker: str
    time: datetime
    timeframe: str
    open: Decimal | float | int
    high: Decimal | float | int
    low: Decimal | float | int
    close: Decimal | float | int
    volume: Decimal | float | int = 0
    source: str = "MOEX"


class IntradayRepository:
    """Repository for minute/intraday OHLCV candles stored in candles_intraday."""

    def upsert_many(self, candles: Iterable[IntradayCandle]) -> int:
        rows = [
            (
                c.time,
                c.ticker.upper(),
                c.timeframe,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
                c.source,
            )
            for c in candles
        ]

        if not rows:
            return 0

        sql = """
            INSERT INTO candles_intraday (
                time, ticker, timeframe, open, high, low, close, volume, source
            ) VALUES %s
            ON CONFLICT (time, ticker, timeframe, source)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                updated_at = NOW()
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                execute_values(cur, sql, rows)
            conn.commit()

        return len(rows)

    def get_range(
        self,
        ticker: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1m",
        source: Optional[str] = None,
    ) -> list[dict]:
        params: list[object] = [ticker.upper(), timeframe, start, end]
        source_filter = ""
        if source:
            source_filter = "AND source = %s"
            params.append(source)

        sql = f"""
            SELECT time, ticker, timeframe, open, high, low, close, volume, source
            FROM candles_intraday
            WHERE ticker = %s
              AND timeframe = %s
              AND time >= %s
              AND time < %s
              {source_filter}
            ORDER BY time ASC
        """

        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def get_latest(
        self,
        ticker: str,
        limit: int = 100,
        timeframe: str = "1m",
        source: Optional[str] = None,
    ) -> list[dict]:
        if limit <= 0:
            return []

        params: list[object] = [ticker.upper(), timeframe]
        source_filter = ""
        if source:
            source_filter = "AND source = %s"
            params.append(source)
        params.append(limit)

        sql = f"""
            SELECT time, ticker, timeframe, open, high, low, close, volume, source
            FROM candles_intraday
            WHERE ticker = %s
              AND timeframe = %s
              {source_filter}
            ORDER BY time DESC
            LIMIT %s
        """

        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = list(cur.fetchall())

        return list(reversed(rows))
