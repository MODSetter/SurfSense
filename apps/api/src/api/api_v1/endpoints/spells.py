from typing import Literal, Optional, Union

from fastapi import APIRouter, HTTPException

from src.api.deps import SessionDep
from src.crud import spell
from src.schemas import Spell, SpellSearchResults

router = APIRouter()


@router.get("/get/", status_code=200, response_model=Spell)
async def get_spell(session: SessionDep, spell_id: str) -> Spell:
    """Returns a spell from a spell_id.

    **Returns:**
    - spell: spell object.
    """
    return await spell.get(session, id=spell_id)


@router.get("/get-all/", status_code=200, response_model=list[Spell])
async def get_all_spells(session: SessionDep) -> list[Spell]:
    """Returns a list of all spells.

    **Returns:**
    - list[spell]: List of all spells.
    """
    return await spell.get_all(session)


@router.get("/search/", status_code=200, response_model=SpellSearchResults)
async def search_spells(
    session: SessionDep,
    search_on: Literal["id", "name", "description"] = "name",
    keyword: Optional[Union[str, int]] = None,
    max_results: Optional[int] = 10,
) -> SpellSearchResults:
    """
    Search for spells based on a keyword and return the top `max_results` items.

    **Args:**
    - search_on (str, optional): The field to perform the search on. Defaults to "name".
    - keyword (str, optional): The keyword to search for. Defaults to None.
    - max_results (int, optional): The maximum number of search results to return. Defaults to 10.

    **Returns:**
    - SpellSearchResults: Object containing a list of the top `max_results` items that match the keyword.
    """
    if not keyword:
        results = await spell.get_all(session)
        return SpellSearchResults(results=results)

    results = await spell.search_all(
        session, field=search_on, search_value=keyword, max_results=max_results
    )

    if not results:
        raise HTTPException(
            status_code=404, detail="No spells found matching the search criteria"
        )

    return SpellSearchResults(results=results)
