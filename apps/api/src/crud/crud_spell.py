from typing import Optional

from fastapi import HTTPException
from supabase_py_async import AsyncClient

from src.crud.base import CRUDBase
from src.schemas import Spell, SpellCreate, SpellUpdate


class CRUDSpell(CRUDBase[Spell, SpellCreate, SpellUpdate]):
    async def get(self, db: AsyncClient, *, id: str) -> Optional[Spell]:
        try:
            return await super().get(db, id=id)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"{e.code}: Spell not found. {e.details}",
            )

    async def get_all(self, db: AsyncClient) -> list[Spell]:
        try:
            return await super().get_all(db)
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"An error occurred while fetching spells. {e}",
            )

    async def search_all(
        self, db: AsyncClient, *, field: str, search_value: str, max_results: int
    ) -> list[Spell]:
        try:
            return await super().search_all(
                db, field=field, search_value=search_value, max_results=max_results
            )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"An error occurred while searching for users. {e}",
            )


spell = CRUDSpell(Spell)
