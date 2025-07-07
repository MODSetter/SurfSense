import datetime
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from app.config import config
from app.services.llm_service import get_user_strategic_llm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, List, Optional


class QueryService:
    """
    Service for query-related operations, including reformulation and processing.
    """

    @staticmethod
    async def reformulate_query_with_chat_history(
        user_query: str, 
        session: AsyncSession, 
        user_id: str, 
        chat_history_str: Optional[str] = None
    ) -> str:
        """
        Reformulate the user query using the user's strategic LLM to make it more 
        effective for information retrieval and research purposes.

        Args:
            user_query: The original user query
            session: Database session for accessing user LLM configs
            user_id: User ID to get their specific LLM configuration
            chat_history_str: Optional chat history string

        Returns:
            str: The reformulated query
        """
        if not user_query or not user_query.strip():
            return user_query

        try:
            # Get the user's strategic LLM instance
            llm = await get_user_strategic_llm(session, user_id)
            if not llm:
                print(f"Warning: No strategic LLM configured for user {user_id}. Using original query.")
                return user_query

            # Create system message with instructions
            system_message = SystemMessage(
                content=f"""
                Today's date: {datetime.datetime.now().strftime("%Y-%m-%d")}
                You are a highly skilled AI assistant specializing in query optimization for advanced research.
                Your primary objective is to transform a user's initial query into a highly effective search query.
                This reformulated query will be used to retrieve information from diverse data sources.

                **Chat History Context:**
                {chat_history_str if chat_history_str else "No prior conversation history is available."}
                If chat history is provided, analyze it to understand the user's evolving information needs and the broader context of their request. Use this understanding to refine the current query, ensuring it builds upon or clarifies previous interactions.

                **Query Reformulation Guidelines:**
                Your reformulated query should:
                1.  **Enhance Specificity and Detail:** Add precision to narrow the search focus effectively, making the query less ambiguous and more targeted.
                2.  **Resolve Ambiguities:** Identify and clarify vague terms or phrases. If a term has multiple meanings, orient the query towards the most likely one given the context.
                3.  **Expand Key Concepts:** Incorporate relevant synonyms, related terms, and alternative phrasings for core concepts. This helps capture a wider range of relevant documents.
                4.  **Deconstruct Complex Questions:** If the original query is multifaceted, break it down into its core searchable components or rephrase it to address each aspect clearly. The final output must still be a single, coherent query string.
                5.  **Optimize for Comprehensiveness:** Ensure the query is structured to uncover all essential facets of the original request, aiming for thorough information retrieval suitable for research.
                6.  **Maintain User Intent:** The reformulated query must stay true to the original intent of the user's query. Do not introduce new topics or shift the focus significantly.

                **Crucial Constraints:**
                *   **Conciseness and Effectiveness:** While aiming for comprehensiveness, the reformulated query MUST be as concise as possible. Eliminate all unnecessary verbosity. Focus on essential keywords, entities, and concepts that directly contribute to effective retrieval.
                *   **Single, Direct Output:** Return ONLY the reformulated query itself. Do NOT include any explanations, introductory phrases (e.g., "Reformulated query:", "Here is the optimized query:"), or any other surrounding text or markdown formatting.

                Your output should be a single, optimized query string, ready for immediate use in a search system.
                """
            )

            # Create human message with the user query
            human_message = HumanMessage(
                content=f"Reformulate this query for better research results: {user_query}"
            )

            # Get the response from the LLM
            response = await llm.agenerate(messages=[[system_message, human_message]])

            # Extract the reformulated query from the response
            reformulated_query = response.generations[0][0].text.strip()

            # Return the original query if the reformulation is empty
            if not reformulated_query:
                return user_query

            return reformulated_query

        except Exception as e:
            # Log the error and return the original query
            print(f"Error reformulating query: {e}")
            return user_query


    @staticmethod
    async def langchain_chat_history_to_str(chat_history: List[Any]) -> str:
        """
        Convert a list of chat history messages to a string.
        """
        chat_history_str = "<chat_history>\n"
        
        for chat_message in chat_history:
            if isinstance(chat_message, HumanMessage):
                chat_history_str += f"<user>{chat_message.content}</user>\n"
            elif isinstance(chat_message, AIMessage):
                chat_history_str += f"<assistant>{chat_message.content}</assistant>\n"
            elif isinstance(chat_message, SystemMessage):
                chat_history_str += f"<system>{chat_message.content}</system>\n"
                
        chat_history_str += "</chat_history>"
        return chat_history_str
