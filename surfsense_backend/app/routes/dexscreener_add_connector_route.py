import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    get_async_session,
)
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


class TokenConfig(BaseModel):
    """Configuration for a single token to track."""

    chain: str = Field(..., description="Blockchain network (e.g., ethereum, bsc, solana)", pattern=r"^[a-z0-9-]+$")
    address: str = Field(..., description="Token contract address")
    name: str | None = Field(None, description="Optional token name for display")
    
    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate token address format (EVM or Solana)."""
        # EVM address: 0x + 40 hex characters
        if v.startswith("0x"):
            if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
                raise ValueError("Invalid EVM address format. Must be 0x followed by 40 hex characters.")
            return v
        # Solana address: 32-44 base58 characters
        if len(v) < 32 or len(v) > 44:
            raise ValueError("Invalid Solana address format. Must be 32-44 characters.")
        # Allow base58 chars only for Solana
        if not re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", v):
            raise ValueError("Invalid Solana address format. Contains invalid characters.")
        return v


class AddDexScreenerConnectorRequest(BaseModel):
    """Request model for adding a DexScreener connector."""

    tokens: list[TokenConfig] = Field(
        ..., description="List of tokens to track (max 50)", min_length=1, max_length=50
    )
    space_id: int = Field(..., description="Search space ID")


@router.post("/connectors/dexscreener/add")
async def add_dexscreener_connector(
    request: AddDexScreenerConnectorRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Add a new DexScreener connector for the authenticated user.

    Args:
        request: The request containing tokens configuration and space_id
        user: Current authenticated user
        session: Database session

    Returns:
        Success message and connector details

    Raises:
        HTTPException: If connector already exists or validation fails
    """
    try:
        # Check if a DexScreener connector already exists for this search space and user
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == request.space_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            )
        )
        existing_connector = result.scalars().first()

        # Convert tokens to dict format for storage
        tokens_config = [token.model_dump() for token in request.tokens]

        if existing_connector:
            # Update existing connector with new tokens
            existing_connector.config = {"tokens": tokens_config}
            existing_connector.is_indexable = True
            await session.commit()
            await session.refresh(existing_connector)

            logger.info(
                f"Updated existing DexScreener connector for user {user.id} in space {request.space_id}"
            )

            return {
                "message": "DexScreener connector updated successfully",
                "connector_id": existing_connector.id,
                "connector_type": "DEXSCREENER_CONNECTOR",
                "tokens_count": len(tokens_config),
            }

        # Create new DexScreener connector
        db_connector = SearchSourceConnector(
            name="DexScreener Connector",
            connector_type=SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            config={"tokens": tokens_config},
            search_space_id=request.space_id,
            user_id=user.id,
            is_indexable=True,
        )

        session.add(db_connector)
        await session.commit()
        await session.refresh(db_connector)

        logger.info(
            f"Successfully created DexScreener connector for user {user.id} with ID {db_connector.id}"
        )

        return {
            "message": "DexScreener connector added successfully",
            "connector_id": db_connector.id,
            "connector_type": "DEXSCREENER_CONNECTOR",
            "tokens_count": len(tokens_config),
        }

    except IntegrityError as e:
        await session.rollback()
        logger.error(f"Database integrity error: {e!s}")
        raise HTTPException(
            status_code=409,
            detail="A DexScreener connector already exists for this user.",
        ) from e
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error adding DexScreener connector: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add DexScreener connector: {e!s}",
        ) from e


@router.delete("/connectors/dexscreener")
async def delete_dexscreener_connector(
    space_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Delete the DexScreener connector for the authenticated user in a specific search space.

    Args:
        space_id: Search space ID
        user: Current authenticated user
        session: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If connector doesn't exist
    """
    try:
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="DexScreener connector not found for this user.",
            )

        await session.delete(connector)
        await session.commit()

        logger.info(f"Successfully deleted DexScreener connector for user {user.id}")

        return {"message": "DexScreener connector deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error deleting DexScreener connector: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete DexScreener connector: {e!s}",
        ) from e


@router.get("/connectors/dexscreener/test")
async def test_dexscreener_connector(
    space_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Test the DexScreener connector for the authenticated user in a specific search space.

    Args:
        space_id: Search space ID
        user: Current authenticated user
        session: Database session

    Returns:
        Test results including token count and sample pair data

    Raises:
        HTTPException: If connector doesn't exist or test fails
    """
    try:
        # Get the DexScreener connector for this search space and user
        result = await session.execute(
            select(SearchSourceConnector).filter(
                SearchSourceConnector.search_space_id == space_id,
                SearchSourceConnector.user_id == user.id,
                SearchSourceConnector.connector_type
                == SearchSourceConnectorType.DEXSCREENER_CONNECTOR,
            )
        )
        connector = result.scalars().first()

        if not connector:
            raise HTTPException(
                status_code=404,
                detail="DexScreener connector not found. Please add a connector first.",
            )

        # Import DexScreenerConnector
        from app.connectors.dexscreener_connector import DexScreenerConnector

        # Initialize the connector
        tokens = connector.config.get("tokens", [])
        if not tokens:
            raise HTTPException(
                status_code=400,
                detail="Invalid connector configuration: No tokens configured.",
            )

        dexscreener = DexScreenerConnector()

        # Test the connection by fetching pairs for the first token
        first_token = tokens[0]
        chain = first_token.get("chain")
        address = first_token.get("address")
        token_name = first_token.get("name", "Unknown")

        if not chain or not address:
            raise HTTPException(
                status_code=400,
                detail="Invalid token configuration: Missing chain or address.",
            )

        # Try to fetch pairs for the first token
        pairs, error = await dexscreener.get_token_pairs(chain, address)

        if error:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to connect to DexScreener: {error}",
            )

        # Get sample pair info if available
        sample_pair = None
        if pairs and len(pairs) > 0:
            pair = pairs[0]
            base_token = pair.get("baseToken", {})
            quote_token = pair.get("quoteToken", {})
            sample_pair = {
                "pair_address": pair.get("pairAddress"),
                "base_symbol": base_token.get("symbol", "Unknown"),
                "quote_symbol": quote_token.get("symbol", "Unknown"),
                "dex": pair.get("dexId", "Unknown"),
                "price_usd": pair.get("priceUsd", "N/A"),
                "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
            }

        return {
            "message": "DexScreener connector is working correctly",
            "tokens_configured": len(tokens),
            "test_token": {
                "name": token_name,
                "chain": chain,
                "address": address,
            },
            "pairs_found": len(pairs) if pairs else 0,
            "sample_pair": sample_pair,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error testing DexScreener connector: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test DexScreener connector: {e!s}",
        ) from e
