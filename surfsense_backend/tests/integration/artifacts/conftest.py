import pytest_asyncio

from app.db import NewChatThread


@pytest_asyncio.fixture
async def artifact_thread_factory(db_session, db_workspace):
    async def create(title: str = "Artifact test thread"):
        thread = NewChatThread(
            title=title,
            workspace_id=db_workspace.id,
            created_by_id=db_workspace.user_id,
        )
        db_session.add(thread)
        await db_session.flush()
        return thread

    return create


@pytest_asyncio.fixture
async def artifact_thread(artifact_thread_factory):
    return await artifact_thread_factory()
