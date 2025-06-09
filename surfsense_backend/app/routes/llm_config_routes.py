from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from pydantic import BaseModel
from app.db import get_async_session, User, LLMConfig
from app.schemas import LLMConfigCreate, LLMConfigUpdate, LLMConfigRead
from app.users import current_active_user
from app.utils.check_ownership import check_ownership

router = APIRouter()

class LLMPreferencesUpdate(BaseModel):
    """Schema for updating user LLM preferences"""
    long_context_llm_id: Optional[int] = None
    fast_llm_id: Optional[int] = None
    strategic_llm_id: Optional[int] = None

class LLMPreferencesRead(BaseModel):
    """Schema for reading user LLM preferences"""
    long_context_llm_id: Optional[int] = None
    fast_llm_id: Optional[int] = None
    strategic_llm_id: Optional[int] = None
    long_context_llm: Optional[LLMConfigRead] = None
    fast_llm: Optional[LLMConfigRead] = None
    strategic_llm: Optional[LLMConfigRead] = None

@router.post("/llm-configs/", response_model=LLMConfigRead)
async def create_llm_config(
    llm_config: LLMConfigCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Create a new LLM configuration for the authenticated user"""
    try:
        db_llm_config = LLMConfig(**llm_config.model_dump(), user_id=user.id)
        session.add(db_llm_config)
        await session.commit()
        await session.refresh(db_llm_config)
        return db_llm_config
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create LLM configuration: {str(e)}"
        )

@router.get("/llm-configs/", response_model=List[LLMConfigRead])
async def read_llm_configs(
    skip: int = 0,
    limit: int = 200,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get all LLM configurations for the authenticated user"""
    try:
        result = await session.execute(
            select(LLMConfig)
            .filter(LLMConfig.user_id == user.id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch LLM configurations: {str(e)}"
        )

@router.get("/llm-configs/{llm_config_id}", response_model=LLMConfigRead)
async def read_llm_config(
    llm_config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get a specific LLM configuration by ID"""
    try:
        llm_config = await check_ownership(session, LLMConfig, llm_config_id, user)
        return llm_config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch LLM configuration: {str(e)}"
        )

@router.put("/llm-configs/{llm_config_id}", response_model=LLMConfigRead)
async def update_llm_config(
    llm_config_id: int,
    llm_config_update: LLMConfigUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Update an existing LLM configuration"""
    try:
        db_llm_config = await check_ownership(session, LLMConfig, llm_config_id, user)
        update_data = llm_config_update.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(db_llm_config, key, value)
            
        await session.commit()
        await session.refresh(db_llm_config)
        return db_llm_config
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update LLM configuration: {str(e)}"
        )

@router.delete("/llm-configs/{llm_config_id}", response_model=dict)
async def delete_llm_config(
    llm_config_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Delete an LLM configuration"""
    try:
        db_llm_config = await check_ownership(session, LLMConfig, llm_config_id, user)
        await session.delete(db_llm_config)
        await session.commit()
        return {"message": "LLM configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete LLM configuration: {str(e)}"
        )

# User LLM Preferences endpoints

@router.get("/users/me/llm-preferences", response_model=LLMPreferencesRead)
async def get_user_llm_preferences(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Get the current user's LLM preferences"""
    try:
        # Refresh user to get latest relationships
        await session.refresh(user)
        
        result = {
            "long_context_llm_id": user.long_context_llm_id,
            "fast_llm_id": user.fast_llm_id,
            "strategic_llm_id": user.strategic_llm_id,
            "long_context_llm": None,
            "fast_llm": None,
            "strategic_llm": None,
        }
        
        # Fetch the actual LLM configs if they exist
        if user.long_context_llm_id:
            long_context_llm = await session.execute(
                select(LLMConfig).filter(
                    LLMConfig.id == user.long_context_llm_id,
                    LLMConfig.user_id == user.id
                )
            )
            llm_config = long_context_llm.scalars().first()
            if llm_config:
                result["long_context_llm"] = llm_config
        
        if user.fast_llm_id:
            fast_llm = await session.execute(
                select(LLMConfig).filter(
                    LLMConfig.id == user.fast_llm_id,
                    LLMConfig.user_id == user.id
                )
            )
            llm_config = fast_llm.scalars().first()
            if llm_config:
                result["fast_llm"] = llm_config
        
        if user.strategic_llm_id:
            strategic_llm = await session.execute(
                select(LLMConfig).filter(
                    LLMConfig.id == user.strategic_llm_id,
                    LLMConfig.user_id == user.id
                )
            )
            llm_config = strategic_llm.scalars().first()
            if llm_config:
                result["strategic_llm"] = llm_config
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch LLM preferences: {str(e)}"
        )

@router.put("/users/me/llm-preferences", response_model=LLMPreferencesRead)
async def update_user_llm_preferences(
    preferences: LLMPreferencesUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    """Update the current user's LLM preferences"""
    try:
        # Validate that all provided LLM config IDs belong to the user
        update_data = preferences.model_dump(exclude_unset=True)
        
        for key, llm_config_id in update_data.items():
            if llm_config_id is not None:
                # Verify ownership of the LLM config
                result = await session.execute(
                    select(LLMConfig).filter(
                        LLMConfig.id == llm_config_id,
                        LLMConfig.user_id == user.id
                    )
                )
                llm_config = result.scalars().first()
                if not llm_config:
                    raise HTTPException(
                        status_code=404,
                        detail=f"LLM configuration {llm_config_id} not found or you don't have permission to access it"
                    )
        
        # Update user preferences
        for key, value in update_data.items():
            setattr(user, key, value)
        
        await session.commit()
        await session.refresh(user)
        
        # Return updated preferences
        return await get_user_llm_preferences(session, user)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update LLM preferences: {str(e)}"
        ) 