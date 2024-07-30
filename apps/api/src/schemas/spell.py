from typing import ClassVar, Sequence

from pydantic import BaseModel


class Spell(BaseModel):
    id: str
    name: str
    description: str
    table_name: ClassVar[str] = "spells"


class SpellCreate(BaseModel):
    id: str
    name: str
    description: str


class SpellUpdate(BaseModel):
    id: str
    name: str
    description: str


class SpellSearchResults(BaseModel):
    results: Sequence[Spell]
