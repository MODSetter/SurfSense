from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db import User

# Helper function to check user ownership
async def check_ownership(session: AsyncSession, model, item_id: int, user: User):
    item = await session.execute(select(model).filter(model.id == item_id, model.user_id == user.id))
    item = item.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found or you don't have permission to access it")
    return item 