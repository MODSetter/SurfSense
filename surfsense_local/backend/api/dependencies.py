from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool


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


async def transact[T](session: Session, work: Callable[..., T], *args: object) -> T:
    """Session work from an `async def` handler: off the event loop, committed at once.

    A `def` handler already runs in the threadpool and may use the session
    freely. An `async def` handler may not: SQLite waits for the write lock on
    the calling thread, and no transaction may stay open across an `await`
    (the lock is taken at BEGIN and held until commit). So the handler passes
    each stretch of session work here and awaits nothing else in between.
    """

    def run() -> T:
        result = work(session, *args)
        session.commit()
        return result

    return await run_in_threadpool(run)
