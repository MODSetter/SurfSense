import os
import logging
from uuid import uuid4
from sqlalchemy.future import select
from app.db import async_session_maker, User, SearchSpace
from .markdown_processor import add_received_markdown_file_document

async def index_alison_docs():
    """
    Indexes the documents in the alison_docs directory.
    """
    async with async_session_maker() as session:
        try:
            # 1. Create or get the "alison" user
            result = await session.execute(select(User).where(User.email == "alison@surfsense.ai"))
            alison_user = result.scalars().first()

            if not alison_user:
                alison_user = User(
                    id=uuid4(),
                    email="alison@surfsense.ai",
                    hashed_password="dummy_password", # This should be handled more securely in a real application
                    is_active=True,
                    is_superuser=False,
                    is_verified=True,
                )
                session.add(alison_user)
                await session.commit()
                await session.refresh(alison_user)

            # 2. Create or get the "Alison's Knowledge Base" search space
            result = await session.execute(select(SearchSpace).where(SearchSpace.name == "Alison's Knowledge Base"))
            alison_search_space = result.scalars().first()

            if not alison_search_space:
                alison_search_space = SearchSpace(
                    name="Alison's Knowledge Base",
                    description="Knowledge base for the Alison IT support assistant.",
                    user_id=alison_user.id,
                )
                session.add(alison_search_space)
                await session.commit()
                await session.refresh(alison_search_space)

            # 3. Index the documents
            alison_docs_dir = "app/alison_docs"
            for filename in os.listdir(alison_docs_dir):
                if filename.endswith(".md"):
                    filepath = os.path.join(alison_docs_dir, filename)
                    with open(filepath, "r") as f:
                        content = f.read()

                    await add_received_markdown_file_document(
                        session=session,
                        file_name=filename,
                        file_in_markdown=content,
                        search_space_id=alison_search_space.id,
                        user_id=str(alison_user.id),
                    )
            logging.info("Alison's knowledge base indexed successfully.")
        except Exception as e:
            logging.error(f"Failed to index Alison's knowledge base: {e}")
            await session.rollback()
