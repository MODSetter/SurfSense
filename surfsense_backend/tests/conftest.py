"""Shared pytest fixtures for SurfSense backend tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture
async def async_session():
    """Create an async database session for testing."""
    from sqlalchemy import JSON, ARRAY, event
    from sqlalchemy.dialects.postgresql import JSONB
    
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Replace JSONB and ARRAY with JSON for SQLite compatibility
    @event.listens_for(Base.metadata, "before_create")
    def _set_json_type(target, connection, **kw):
        for table in Base.metadata.tables.values():
            for column in table.columns:
                # Convert JSONB to JSON
                if isinstance(column.type, type(JSONB())):
                    column.type = JSON()
                # Convert ARRAY to JSON (SQLite doesn't support ARRAY)
                elif isinstance(column.type, ARRAY):
                    column.type = JSON()

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
def mock_connector_config():
    """Mock connector configuration."""
    return {
        "tokens": [
            {
                "chain": "ethereum",
                "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "name": "WETH",
            },
            {
                "chain": "solana",
                "address": "So11111111111111111111111111111111111111112",
                "name": "SOL",
            },
        ]
    }


@pytest.fixture
def mock_pair_data():
    """Mock DexScreener API response data."""
    return {
        "pairs": [
            {
                "chainId": "ethereum",
                "dexId": "uniswap",
                "url": "https://dexscreener.com/ethereum/0x123",
                "pairAddress": "0x123",
                "baseToken": {
                    "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                    "name": "Wrapped Ether",
                    "symbol": "WETH",
                },
                "quoteToken": {
                    "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "name": "USD Coin",
                    "symbol": "USDC",
                },
                "priceNative": "1.0",
                "priceUsd": "2500.00",
                "txns": {
                    "m5": {"buys": 10, "sells": 5},
                    "h1": {"buys": 100, "sells": 50},
                    "h6": {"buys": 500, "sells": 250},
                    "h24": {"buys": 2000, "sells": 1000},
                },
                "volume": {"h24": 1000000.0, "h6": 250000.0, "h1": 50000.0, "m5": 5000.0},
                "priceChange": {"m5": 0.5, "h1": 1.2, "h6": 2.5, "h24": 5.0},
                "liquidity": {"usd": 5000000.0, "base": 2000.0, "quote": 5000000.0},
                "fdv": 10000000.0,
                "pairCreatedAt": 1609459200000,
            }
        ]
    }
