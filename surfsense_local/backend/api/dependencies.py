from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """One session per request, committed only if the handler returned cleanly."""
    with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        else:
            session.commit()


SessionDep = Annotated[Session, Depends(get_session)]
