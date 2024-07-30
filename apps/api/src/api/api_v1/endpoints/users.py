from typing import Literal, Optional, Union

from fastapi import APIRouter, HTTPException

from src.api.deps import SessionDep
from src.crud import user
from src.schemas import User, UserCreate, UserSearchResults

router = APIRouter()


@router.get("/get/", status_code=200, response_model=User)
async def get_user(session: SessionDep, user_id: str) -> User:
    """Returns a user from a user_id.

    **Returns:**
    - User: User object.
    """
    return await user.get(session, id=user_id)


@router.get("/get-all/", status_code=200, response_model=list[User])
async def get_all_users(session: SessionDep) -> list[User]:
    """Returns a list of all users.

    **Returns:**
    - list[User]: List of all users.
    """
    return await user.get_all(session)


@router.get("/search/", status_code=200, response_model=UserSearchResults)
async def search_users(
    session: SessionDep,
    search_on: Literal["id", "email", "forename", "surname"] = "email",
    keyword: Optional[Union[str, int]] = None,
    max_results: Optional[int] = 10,
) -> UserSearchResults:
    """
    Search for users based on a keyword and return the top `max_results` items.

    **Args:**
    - keyword (str, optional): The keyword to search for. Defaults to None.
    - max_results (int, optional): The maximum number of search results to return. Defaults to 10.
    - search_on (str, optional): The field to perform the search on. Defaults to "email".

    **Returns:**
    - UserSearchResults: Object containing a list of the top `max_results` items that match the keyword.
    """
    if not keyword:
        results = await user.get_all(session)
        return UserSearchResults(results=results)

    results = await user.search_all(
        session, field=search_on, search_value=keyword, max_results=max_results
    )

    if not results:
        raise HTTPException(
            status_code=404, detail="No users found matching the search criteria"
        )

    return UserSearchResults(results=results)


@router.post("/create", status_code=201, response_model=User)
async def create_user(user_in: UserCreate, session: SessionDep) -> User:
    """Craete a new user.

    **Args:**
    - user_in (UserCreate): JSON of the user to create. Forename, surname and email. Email must be unique.

    **Returns:**
    - User: User object
    """
    return await user.create(session, obj_in=user_in)
