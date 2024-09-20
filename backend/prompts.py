from langchain_core.prompts.prompt import PromptTemplate
from datetime import datetime, timezone




DATE_TODAY = "Today's date is " + datetime.now(timezone.utc).astimezone().isoformat() + '\n'

# Create a prompt template for sub-query decomposition
SUBQUERY_DECOMPOSITION_TEMPLATE = DATE_TODAY + """You are an AI assistant tasked with breaking down complex queries into simpler sub-queries for a vector store.
Given the original query, decompose it into 2-4 simpler sub-queries for vector search that helps in expanding context.

Original query: {original_query}

IMPORTANT INSTRUCTION: Make sure to only return sub-queries and no explanation.

EXAMPLE: 

User Query: What are the impacts of climate change on the environment?

AI Answer: 
What are the impacts of climate change on biodiversity?
How does climate change affect the oceans?
What are the effects of climate change on agriculture?
What are the impacts of climate change on human health?
"""

# SUBQUERY_DECOMPOSITION_TEMPLATE_TWO = DATE_TODAY + """You are an AI language model assistant. Your task is to generate five 
#     different versions of the given user question to retrieve relevant documents from a vector 
#     database. By generating multiple perspectives on the user question, your goal is to help
#     the user overcome some of the limitations of the distance-based similarity search. 
#     Provide these alternative questions separated by newlines.
#     Original question: {original_query}"""


SUBQUERY_DECOMPOSITION_PROMT = PromptTemplate(
    input_variables=["original_query"],
    template=SUBQUERY_DECOMPOSITION_TEMPLATE
)

CONTEXT_ANSWER_TEMPLATE = DATE_TODAY + """You are a phd in english litrature. You are given the task to give detailed research report and explanation to the user query based on the given context.

IMPORTANT INSTRUCTION: Only return answer if you can find it in given context otherwise just say you don't know.

Context: {context}

User Query: {query}
Detailed Report:"""

ANSWER_WITH_CITATIONS = DATE_TODAY + """You're a helpful AI assistant. Given a user question and some Webpage article snippets, \
answer the user question and provide citations. If none of the articles answer the question, just say you don't know.

Remember, you must return both an answer and citations. Citation information is in given Document Metadata.
A citation consists of a “Web Page Title.” Website Name, URL. Accessed Day Month Year.

Citations Example: 
Citations
1. “Citing Sources in Academic Writing.” Scribbr. www.scribbr.com/category/citing-sources/. Accessed 4 March 2021.
2. “What is SEO?” Backlinko. www.backlinko.com/seo. Accessed 10 March 2022.

Here are the Webpage article snippets:
{context}

User Query: {query}
Your Answer:"""


CONTEXT_ANSWER_PROMPT = PromptTemplate(
    input_variables=["context","query"],
    template=ANSWER_WITH_CITATIONS
)










