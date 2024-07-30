from fastapi import APIRouter
from src.api.api_v1.endpoints import users, spells

api_router = APIRouter()
api_router.include_router(users.router, prefix="/users", tags=["users"], responses={404: {"description": "Not found"}})
api_router.include_router(spells.router, prefix="/spells", tags=["spells"], responses={404: {"description": "Not found"}})
