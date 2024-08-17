from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime, timezone




DATE_TODAY = "Today's date is " + datetime.now(timezone.utc).astimezone().isoformat() + '\n'

GRAPH_QUERY_GEN_TEMPLATE = DATE_TODAY + """You are a top tier Prompt Engineering Expert.
A User's Data is stored in a Knowledge Graph.
Your main task is to read the User Question below and give a optimized Question prompt in Natural Language.
Question prompt will be used by a LLM to easlily get data from Knowledge Graph's.

Make sure to only return the promt text thats it. Never change the meaning of users question.

Here are the examples of the User's Data Documents that is stored in Knowledge Graph:
{context}

Note: Do not include any explanations or apologies in your responses.
Do not include any text except the generated promt text.

Question: {question}
Prompt For Cypher Query Construction:"""

GRAPH_QUERY_GEN_PROMPT = PromptTemplate(
    input_variables=["context", "question"], template=GRAPH_QUERY_GEN_TEMPLATE
)

CYPHER_QA_TEMPLATE = DATE_TODAY + """You are an assistant that helps to form nice and human understandable answers.
The information part contains the provided information that you must use to construct an answer.
The provided information is authoritative, you must never doubt it or try to use your internal knowledge to correct it.
Make the answer sound as a response to the question. Do not mention that you based the result on the given information.
Only give the answer if it satisfies the user requirements in Question. Else return exactly 'don't know' as answer.

Here are the examples:

Question: What type of general topics I explore the most?
Context:[['Topic': 'Langchain', 'topicCount': 5], ['Topic': 'Graphrag', 'topicCount': 2], ['Topic': 'Ai', 'topicCount': 2], ['Topic': 'Fastapi', 'topicCount': 2], ['Topic': 'Nextjs', 'topicCount': 1]]
Helpful Answer: You mostly explore about Langchain, Graphrag, Ai, Fastapi and Nextjs.

Follow this example when generating answers.
If the provided information is empty or incomplete, return exactly 'don't know' as answer.

Information:
{context}

Question: {question}
Helpful Answer:"""

CYPHER_QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"], template=CYPHER_QA_TEMPLATE
)

SIMILARITY_SEARCH_RAG = DATE_TODAY + """You are an assistant for question-answering tasks. 
Use the following pieces of retrieved context to answer the question. 
If you don't know the answer, return exactly 'don't know' as answer.
Question: {question} 
Context: {context} 
Answer:"""


SIMILARITY_SEARCH_PROMPT = PromptTemplate(
    input_variables=["context", "question"], template=SIMILARITY_SEARCH_RAG
)

# doc_extract_chain = DOCUMENT_METADATA_EXTRACTION_PROMT | structured_llm


CYPHER_GENERATION_TEMPLATE = DATE_TODAY + """Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Schema:
{schema}
Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
Do not include any text except the generated Cypher statement.

The question is:
{question}"""
CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)


DOC_DESCRIPTION_TEMPLATE = DATE_TODAY + """Task:Give Detailed Description of the page content of the given document.
Instructions:
Provide as much details about metadata & page content as if you need to give human readable report of this Browsing session event. 

Document:
{document}
"""
DOC_DESCRIPTION_PROMPT = PromptTemplate(
    input_variables=["document"], template=DOC_DESCRIPTION_TEMPLATE
)


DOCUMENT_METADATA_EXTRACTION_SYSTEM_MESSAGE = DATE_TODAY + """You are a helpful assistant. You are given a Cypher statement result after quering the Neo4j graph database.
Generate a very good Query that can be used to perform similarity search on the vector store of the Neo4j graph database"""

DOCUMENT_METADATA_EXTRACTION_PROMT = ChatPromptTemplate.from_messages([("system", DOCUMENT_METADATA_EXTRACTION_SYSTEM_MESSAGE), ("human", "{input}")])



VECTOR_QUERY_GENERATION_TEMPLATE = DATE_TODAY + """You are a helpful assistant. You are given a user query and the examples of document on which user is asking query about.
Give instruction to machine how to search for the data based on user query.

Document Examples:
{examples}

Note: Only return the Query and nothing else. No explanation.

User Query: {query}
Helpful Answer:"""

VECTOR_QUERY_GENERATION_PROMT = PromptTemplate(
    input_variables=["examples", "query"], template=VECTOR_QUERY_GENERATION_TEMPLATE
)







