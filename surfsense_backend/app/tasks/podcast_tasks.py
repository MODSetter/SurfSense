
from app.agents.podcaster.graph import graph as podcaster_graph
from app.agents.podcaster.state import State
from app.db import Chat, Podcast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_document_podcast(
    session: AsyncSession,
    document_id: int,
    search_space_id: int,
    user_id: int
):
    # TODO: Need to fetch the document chunks, then concatenate them and pass them to the podcast generation model
    pass



async def generate_chat_podcast(
    session: AsyncSession,
    chat_id: int,
    search_space_id: int,
    podcast_title: str,
    user_id: int
):
    # Fetch the chat with the specified ID
    query = select(Chat).filter(
        Chat.id == chat_id,
        Chat.search_space_id == search_space_id
    )
    
    result = await session.execute(query)
    chat = result.scalars().first()
    
    if not chat:
        raise ValueError(f"Chat with id {chat_id} not found in search space {search_space_id}")
    
    # Create chat history structure
    chat_history_str = "<chat_history>"
    
    for message in chat.messages:
        if message["role"] == "user":
            chat_history_str += f"<user_message>{message['content']}</user_message>"
        elif message["role"] == "assistant":
            # Last annotation type will always be "ANSWER" here
            answer_annotation = message["annotations"][-1]
            answer_text = ""
            if answer_annotation["type"] == "ANSWER":
                answer_text = answer_annotation["content"]
                # If content is a list, join it into a single string
                if isinstance(answer_text, list):
                    answer_text = "\n".join(answer_text)
                chat_history_str += f"<assistant_message>{answer_text}</assistant_message>"
                
    chat_history_str += "</chat_history>"
    
    # Pass it to the SurfSense Podcaster
    config = {
        "configurable": {
            "podcast_title": "SurfSense",
            "user_id": str(user_id),
        }
    }
    # Initialize state with database session and streaming service
    initial_state = State(
        source_content=chat_history_str,
        db_session=session
    )
    
    # Run the graph directly
    result = await podcaster_graph.ainvoke(initial_state, config=config)
    
    # Convert podcast transcript entries to serializable format
    serializable_transcript = []
    for entry in result["podcast_transcript"]:
        serializable_transcript.append({
            "speaker_id": entry.speaker_id,
            "dialog": entry.dialog
        })
    
    # Create a new podcast entry
    podcast = Podcast(
        title=f"{podcast_title}",
        podcast_transcript=serializable_transcript,
        file_location=result["final_podcast_file_path"],
        search_space_id=search_space_id
    )
    
    # Add to session and commit
    session.add(podcast)
    await session.commit()
    await session.refresh(podcast)
    
    return podcast

