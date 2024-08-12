from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime, timezone


DATE_TODAY = "Today's date is " + datetime.now(timezone.utc).astimezone().isoformat() + '\n'

CYPHER_QA_TEMPLATE = DATE_TODAY + """You are an assistant that helps to form nice and human understandable answers.
The information part contains the provided information that you must use to construct an answer.
The provided information is authoritative, you must never doubt it or try to use your internal knowledge to correct it.
Make the answer sound as a response to the question. Do not mention that you based the result on the given information.
Here are the examples:

Question: Website on which the most time was spend on?
Context:[{'d.VisitedWebPageURL': 'https://stackoverflow.com/questions/59873698/the-default-export-is-not-a-react-component-in-page-nextjs', 'totalDuration': 8889167}]
Helpful Answer: You visited https://stackoverflow.com/questions/59873698/the-default-export-is-not-a-react-component-in-page-nextjs for 8889167 milliseconds or 8889.167 seconds.

Follow this example when generating answers.
If the provided information is empty, then and only then, return exactly 'don't know' as answer.

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


DOC_DESCRIPTION_TEMPLATE = """Task:Give Detailed Description of the page content of the given document.
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




