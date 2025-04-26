"""
NOTE: This is not used anymore. Might be removed in the future.
"""
from langchain.schema import HumanMessage, SystemMessage
from app.config import config

class QueryService:
    """
    Service for query-related operations, including reformulation and processing.
    """

    @staticmethod
    async def reformulate_query(user_query: str) -> str:
        """
        Reformulate the user query using the STRATEGIC_LLM to make it more 
        effective for information retrieval and research purposes.
        
        Args:
            user_query: The original user query
            
        Returns:
            str: The reformulated query
        """
        if not user_query or not user_query.strip():
            return user_query
            
        try:
            # Get the strategic LLM instance from config
            llm = config.strategic_llm_instance
            
            # Create system message with instructions
            system_message = SystemMessage(
                content="""
                You are an expert at reformulating user queries to optimize information retrieval. 
                Your job is to take a user query and reformulate it to:
                
                1. Make it more specific and detailed
                2. Expand ambiguous terms
                3. Include relevant synonyms and alternative phrasings
                4. Break down complex questions into their core components
                5. Ensure it's comprehensive for research purposes
                
                The query will be used with the following data sources/connectors:
                - SERPER_API: Web search for retrieving current information from the internet
                - TAVILY_API: Research-focused search API for comprehensive information
                - SLACK_CONNECTOR: Retrieves information from indexed Slack workspace conversations
                - NOTION_CONNECTOR: Retrieves information from indexed Notion documents and databases
                - FILE: Searches through user's uploaded files
                - CRAWLED_URL: Searches through previously crawled web pages
                
                IMPORTANT: Keep the reformulated query as concise as possible while still being effective.
                Avoid unnecessary verbosity and limit the query to only essential terms and concepts.
                
                Please optimize the query to work effectively across these different data sources.
                
                Return ONLY the reformulated query without explanations, prefixes, or commentary.
                Do not include phrases like "Reformulated query:" or any other text except the query itself.
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