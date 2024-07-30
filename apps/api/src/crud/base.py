from typing import Generic, Optional, TypeVar

from supabase_py_async import AsyncClient

from src.schemas.base import CreateBase, ResponseBase, UpdateBase

ModelType = TypeVar("ModelType", bound=ResponseBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=CreateBase)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=UpdateBase)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]):
        """CRUD object with default methods to do CRUD ops

        Args:
            model (type[ModelType]): Model class type
        """
        self.model = model

    async def get(self, db: AsyncClient, *, id: str) -> Optional[ModelType]:
        """get by table_name by id"""
        data, count = (
            await db.table(self.model.table_name).select("*").eq("id", id).execute()
        )
        _, got = data
        return self.model(**got[0]) if got else None

    async def get_all(self, db: AsyncClient) -> list[ModelType]:
        """get all by table_name"""
        data, count = await db.table(self.model.table_name).select("*").execute()
        _, got = data
        return [self.model(**item) for item in got]

    async def search_all(
        self, db: AsyncClient, *, field: str, search_value: str, max_results: int
    ) -> list[ModelType]:
        """search all by table_name"""
        data, count = (
            await db.table(self.model.table_name)
            .select("*")
            .ilike(field, f"%{search_value}%")
            .limit(max_results)
            .execute()
        )
        _, got = data
        return [self.model(**item) for item in got]

    async def create(self, db: AsyncClient, *, obj_in: CreateSchemaType) -> ModelType:
        """create by CreateSchemaType"""
        data, count = (
            await db.table(self.model.table_name).insert(obj_in.model_dump()).execute()
        )
        _, created = data
        return self.model(**created[0])

    async def update(self, db: AsyncClient, *, obj_in: UpdateSchemaType) -> ModelType:
        """update by UpdateSchemaType"""
        data, count = (
            await db.table(self.model.table_name)
            .update(obj_in.model_dump())
            .eq("id", obj_in.id)
            .execute()
        )
        _, updated = data
        return self.model(**updated[0])

    async def delete(self, db: AsyncClient, *, id: str) -> ModelType:
        """remove by UpdateSchemaType"""
        data, count = (
            await db.table(self.model.table_name).delete().eq("id", id).execute()
        )
        _, deleted = data
        return self.model(**deleted[0])
