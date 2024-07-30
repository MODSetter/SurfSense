from typing import Optional

from fastapi import HTTPException
from supabase_py_async import AsyncClient

from src.crud.base import CRUDBase
from src.schemas import User, UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def create(self, db: AsyncClient, *, obj_in: UserCreate) -> User:
        try:
            return await super().create(db, obj_in=obj_in)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"{e.code}: Failed to create user. {e.details}",
            )

    async def get(self, db: AsyncClient, *, id: str) -> Optional[User]:
        try:
            return await super().get(db, id=id)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"{e.code}: User not found. {e.details}",
            )

    async def get_all(self, db: AsyncClient) -> list[User]:
        try:
            return await super().get_all(db)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"An error occurred while fetching users. {e}",
            )

    async def search_all(
        self, db: AsyncClient, *, field: str, search_value: str, max_results: int
    ) -> list[User]:
        try:
            return await super().search_all(
                db, field=field, search_value=search_value, max_results=max_results
            )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"An error occurred while searching for users. {e}",
            )

    async def update(self, db: AsyncClient, *, obj_in: UserUpdate) -> User:
        return await super().update(db, obj_in=obj_in)

    async def delete(self, db: AsyncClient, *, id: str) -> User:
        return await super().delete(db, id=id)


user = CRUDUser(User)
