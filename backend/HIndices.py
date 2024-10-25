import asyncio
from datetime import datetime
from typing import List
from gpt_researcher import GPTResearcher
from langchain_chroma import Chroma
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.docstore.document import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import FlashrankRerank
from sqlalchemy.orm import Session
from fastapi import Depends

from langchain_core.prompts import PromptTemplate

import os
from dotenv import load_dotenv

from pydmodels import AIAnswer, Reference
from database import SessionLocal
from models import Documents, User
from prompts import CONTEXT_ANSWER_PROMPT
load_dotenv()

SMART_LLM = os.environ.get("SMART_LLM")
EMBEDDING = os.environ.get("EMBEDDING")
IS_LOCAL_SETUP = True if SMART_LLM.startswith("ollama") else False


def extract_model_name(model_string: str) -> tuple[str, str]:
    part1, part2 = model_string.split(":", 1)  # Split into two parts at the first colon
    return part2

MODEL_NAME = extract_model_name(SMART_LLM)
EMBEDDING_MODEL = extract_model_name(EMBEDDING)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

class HIndices:
    def __init__(self, username, api_key='local'):
        """
        """
        self.username = username
        if(IS_LOCAL_SETUP == True):
            self.llm = OllamaLLM(model=MODEL_NAME,temperature=0)
            self.embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        else:
            self.llm = ChatOpenAI(temperature=0, model_name=MODEL_NAME, api_key=api_key)
            self.embeddings = OpenAIEmbeddings(api_key=api_key,model=EMBEDDING_MODEL)   
            
        self.summary_store = Chroma(
            collection_name="summary_store",
            embedding_function=self.embeddings,
            persist_directory="./vectorstores/" + username + "/summary_store_db",  # Where to save data locally
        )
        self.detailed_store = Chroma(
            collection_name="detailed_store",
            embedding_function=self.embeddings,
            persist_directory="./vectorstores/" + username + "/detailed_store_db",  # Where to save data locally
        )
        
        # self.summary_store_size = len(self.summary_store.get()['documents'])
        # self.detailed_store_size = len(self.detailed_store.get()['documents'])
    
    def summarize_file_doc(self, page_no, doc, search_space):

        report_template = """
                You are an eagle-eyed researcher, skilled at summarizing lengthy documents with precision and clarity.
        I would like you to assist me in summarizing the following text. Please create a comprehensive summary that captures the main ideas, key details, and essential arguments presented in the text. Your summary should adhere to the following guidelines:

        Length and Depth: Provide a detailed summary that is approximately [insert desired word count or length, e.g., 300-500 words]. Ensure that it is thorough enough to convey the core message without losing important nuances.

        Structure: Organize the summary logically. Use clear headings and subheadings to delineate different sections or themes within the text. This will help in understanding the flow of ideas.

        Key Points: Highlight the main arguments and supporting details. Include any relevant examples or data that reinforce the key points made in the original text.

        Clarity and Conciseness: While the summary should be detailed, it should also be clear and concise. Avoid unnecessary jargon or overly complex language to ensure that the summary is accessible to a broad audience.

        Objective Tone: Maintain an objective and neutral tone throughout the summary. Avoid personal opinions or interpretations; instead, focus on accurately reflecting the author's intended message.

        Conclusion: End the summary with a brief conclusion that encapsulates the overall significance of the text and its implications.

        Please summarize the following text: 
        {document}
        
        
        ==================
        Detailed Summary:
        """


        report_prompt = PromptTemplate(
            input_variables=["document"],
            template=report_template
        )
        
        # Create an LLMChain for sub-query decomposition
        report_chain = report_prompt | self.llm
        
        
        if(IS_LOCAL_SETUP == True):
            
            response = report_chain.invoke({"document": doc})
            
            metadict = {
                    "page": page_no, 
                    "summary": True,
                    "search_space": search_space,
                    }
            
            metadict.update(doc.metadata)
                
            # metadict['languages'] = metadict['languages'][0]
            
            return Document(
                id=str(page_no),
                page_content=response,
                metadata=metadict
            )     
            
        else:
            response = report_chain.invoke({"document": doc})
            
            metadict = {
                    "page": page_no, 
                    "summary": True,
                    "search_space": search_space,
                    }
            
            metadict.update(doc.metadata)
                
            # metadict['languages'] = metadict['languages'][0]
            
            return Document(
                id=str(page_no),
                page_content=response.content,
                metadata=metadict
            )      
        
    def summarize_webpage_doc(self, page_no, doc, search_space):

        
        report_template = """
        You are an eagle-eyed researcher, skilled at summarizing lengthy documents with precision and clarity.
        I would like you to assist me in summarizing the following text. Please create a comprehensive summary that captures the main ideas, key details, and essential arguments presented in the text. Your summary should adhere to the following guidelines:

        Length and Depth: Provide a detailed summary that is approximately [insert desired word count or length, e.g., 300-500 words]. Ensure that it is thorough enough to convey the core message without losing important nuances.

        Structure: Organize the summary logically. Use clear headings and subheadings to delineate different sections or themes within the text. This will help in understanding the flow of ideas.

        Key Points: Highlight the main arguments and supporting details. Include any relevant examples or data that reinforce the key points made in the original text.

        Clarity and Conciseness: While the summary should be detailed, it should also be clear and concise. Avoid unnecessary jargon or overly complex language to ensure that the summary is accessible to a broad audience.

        Objective Tone: Maintain an objective and neutral tone throughout the summary. Avoid personal opinions or interpretations; instead, focus on accurately reflecting the author's intended message.

        Conclusion: End the summary with a brief conclusion that encapsulates the overall significance of the text and its implications.

        Please summarize the following text: 
        {document}
        
        
        ==================
        Detailed Summary:
        """


        report_prompt = PromptTemplate(
            input_variables=["document"],
            template=report_template
        )
        
        # Create an LLMChain for sub-query decomposition
        report_chain = report_prompt | self.llm
        
        
        if(IS_LOCAL_SETUP == True):
            response = report_chain.invoke({"document": doc})
            
            return Document(
                id=str(page_no),
                page_content=response,
                metadata={
                    "filetype": 'WEBPAGE',
                    "page": page_no, 
                    "summary": True,
                    "search_space": search_space,
                    "BrowsingSessionId": doc.metadata['BrowsingSessionId'],
                    "VisitedWebPageURL": doc.metadata['VisitedWebPageURL'],
                    "VisitedWebPageTitle": doc.metadata['VisitedWebPageTitle'],
                    "VisitedWebPageDateWithTimeInISOString": doc.metadata['VisitedWebPageDateWithTimeInISOString'],
                    "VisitedWebPageReffererURL": doc.metadata['VisitedWebPageReffererURL'],
                    "VisitedWebPageVisitDurationInMilliseconds": doc.metadata['VisitedWebPageVisitDurationInMilliseconds'],
                    }
            ) 
            
        else:
            response = report_chain.invoke({"document": doc})
            
            return Document(
                id=str(page_no),
                page_content=response.content,
                metadata={
                    "filetype": 'WEBPAGE',
                    "page": page_no, 
                    "summary": True,
                    "search_space": search_space,
                    "BrowsingSessionId": doc.metadata['BrowsingSessionId'],
                    "VisitedWebPageURL": doc.metadata['VisitedWebPageURL'],
                    "VisitedWebPageTitle": doc.metadata['VisitedWebPageTitle'],
                    "VisitedWebPageDateWithTimeInISOString": doc.metadata['VisitedWebPageDateWithTimeInISOString'],
                    "VisitedWebPageReffererURL": doc.metadata['VisitedWebPageReffererURL'],
                    "VisitedWebPageVisitDurationInMilliseconds": doc.metadata['VisitedWebPageVisitDurationInMilliseconds'],
                    }
            )
         
    def encode_docs_hierarchical(self, documents, files_type, search_space='GENERAL', db: Session = Depends(get_db)):
        """
        Creates and Saves/Updates docs in hierarchical indices and postgres table
        """

        prev_doc_idx = len(documents) + 1
        # #Save docs in PG
        user = db.query(User).filter(User.username == self.username).first()
        
        if(len(user.documents) < prev_doc_idx):
            summary_last_id = 0
            detail_id_counter = 0
        else:
            summary_last_id = int(user.documents[-prev_doc_idx].id)
            detail_id_counter = int(user.documents[-prev_doc_idx].desc_vector_end)
            
             
        # Process documents
        summaries = []
        if(files_type=='WEBPAGE'):
            batch_summaries = [self.summarize_webpage_doc(page_no = i + summary_last_id, doc=doc, search_space=search_space) for i, doc in enumerate(documents)]
        else:
            batch_summaries = [self.summarize_file_doc(page_no = i + summary_last_id, doc=doc, search_space=search_space) for i, doc in enumerate(documents)]
            
      
        summaries.extend(batch_summaries)
        
        detailed_chunks = []
        
        for i, summary in enumerate(summaries):
            
            # Semantic chucking for better contexual compression
            text_splitter = SemanticChunker(embeddings=self.embeddings)
            chunks = text_splitter.split_documents([documents[i]])
            
            user.documents[-(len(summaries) - i)].desc_vector_start = detail_id_counter
            user.documents[-(len(summaries) - i)].desc_vector_end = detail_id_counter + len(chunks)

            
            db.commit()

            # Update metadata for detailed chunks
            for i, chunk in enumerate(chunks):
                chunk.id = str(detail_id_counter)
                chunk.metadata.update({
                    "chunk_id": detail_id_counter,
                    "summary": False,
                    "page": summary.metadata['page'],
                })
                
                if(files_type == 'WEBPAGE'):
                    ieee_content = (
                    f"=======================================DOCUMENT METADATA==================================== \n"
                    f"Source: {chunk.metadata['VisitedWebPageURL']} \n"
                    f"Title: {chunk.metadata['VisitedWebPageTitle']} \n"
                    f"Visited Date and Time : {chunk.metadata['VisitedWebPageDateWithTimeInISOString']} \n"
                    f"============================DOCUMENT PAGE CONTENT CHUNK===================================== \n"
                    f"Page Content Chunk: \n\n{chunk.page_content}\n\n"
                    f"===================================================================================== \n"
                    )
                    
                else:
                      ieee_content = (
                    f"=======================================DOCUMENT METADATA==================================== \n"
                    f"Source: {chunk.metadata['filename']} \n"
                    f"Title: {chunk.metadata['filename']} \n"
                    f"Visited Date and Time : {datetime.now()} \n"
                    f"============================DOCUMENT PAGE CONTENT CHUNK===================================== \n"
                    f"Page Content Chunk: \n\n{chunk.page_content}\n\n"
                    f"===================================================================================== \n"
                    )
                
                chunk.page_content = ieee_content
                
                detail_id_counter += 1
                
            detailed_chunks.extend(chunks)
            
        #update vector stores
        self.summary_store.add_documents(filter_complex_metadata(summaries))
        self.detailed_store.add_documents(filter_complex_metadata(detailed_chunks))

        return self.summary_store, self.detailed_store
    
    def delete_vector_stores(self, summary_ids_to_delete: list[str], db: Session = Depends(get_db)):
        self.summary_store.delete(ids=summary_ids_to_delete)
        for id in summary_ids_to_delete:
            summary_entry = db.query(Documents).filter(Documents.id == int(id) + 1).first()
            
            desc_ids_to_del = [str(id) for id in range(summary_entry.desc_vector_start, summary_entry.desc_vector_end)]
            
            self.detailed_store.delete(ids=desc_ids_to_del)
            db.delete(summary_entry)
            db.commit()
        
        return "success"
                           
    def summary_vector_search(self,query, search_space='GENERAL'):
        top_summaries_compressor = FlashrankRerank(top_n=20)
        
        top_summaries_retreiver = ContextualCompressionRetriever(
            base_compressor=top_summaries_compressor, base_retriever=self.summary_store.as_retriever(search_kwargs={'filter': {'search_space': search_space}})
        )
        
        return top_summaries_retreiver.invoke(query)
        
    def deduplicate_references_and_update_answer(self, answer: str, references: List[Reference]) -> tuple[str, List[Reference]]:
        """
        Deduplicates references and updates the answer text to maintain correct reference numbering.
        
        Args:
            answer: The text containing reference citations
            references: List of Reference objects
            
        Returns:
            tuple: (updated_answer, deduplicated_references)
        """
        # Track unique references and create ID mapping using a dictionary comprehension
        unique_refs = {}
        id_mapping = {
            ref.id: unique_refs.setdefault(
                ref.url, Reference(id=str(len(unique_refs) + 1), title=ref.title, url=ref.url)
            ).id
            for ref in references
        }

        # Apply new mappings to the answer text
        updated_answer = answer
        for old_id, new_id in sorted(id_mapping.items(), key=lambda x: len(x[0]), reverse=True):
            updated_answer = updated_answer.replace(f'[{old_id}]', f'[{new_id}]')
        
        return updated_answer, list(unique_refs.values())

    async def get_vectorstore_report(self, query: str, report_type: str, report_source: str, documents: List[Document]) -> str:
        researcher = GPTResearcher(query=query, report_type=report_type, report_source=report_source, documents=documents, report_format="IEEE")
        await researcher.conduct_research()
        report = await researcher.write_report()
        return report

    async def get_web_report(self, query: str, report_type: str, report_source: str) -> str:
        researcher = GPTResearcher(query=query, report_type=report_type, report_source=report_source, report_format="IEEE")
        await researcher.conduct_research()
        report = await researcher.write_report()
        return report

    def new_search(self, query, search_space='GENERAL'):
        report_type = "custom_report"
        report_source = "langchain_documents"
        contextdocs = []
        


        top_summaries_compressor = FlashrankRerank(top_n=5)
        details_compressor = FlashrankRerank(top_n=50)
        top_summaries_retreiver = ContextualCompressionRetriever(
            base_compressor=top_summaries_compressor, base_retriever=self.summary_store.as_retriever(search_kwargs={'filter': {'search_space': search_space}})#
        )
        
        top_summaries_compressed_docs = top_summaries_retreiver.invoke(query)
        
        for summary in top_summaries_compressed_docs:
            # For each summary, retrieve relevant detailed chunks
            page_number = summary.metadata["page"]

            detailed_compression_retriever = ContextualCompressionRetriever(
                base_compressor=details_compressor, base_retriever=self.detailed_store.as_retriever(search_kwargs={'filter': {'page': page_number}})
            )
            
            detailed_compressed_docs = detailed_compression_retriever.invoke(
                query
            )
            
            contextdocs.extend(detailed_compressed_docs)
        
        custom_prompt = """
        Please answer the following user query in the format shown below, using in-text citations and IEEE-style references based on the provided documents. 
        USER QUERY : """+ query +"""
        
        Ensure the answer includes:
        - A detailed yet concise explanation with IEEE-style in-text citations (e.g., [1], [2]).
        - A list of non-duplicated sources at the end, following IEEE format. Hyperlink each source using: [Website Name](URL).
        - Where applicable, provide sources in the text to back up key points.
        
        FOR EXAMPLE:
        User Query : Explain the impact of artificial intelligence on modern healthcare.
        
        Given Documents:
            =======================================DOCUMENT METADATA==================================== \n"
            Source: https://www.reddit.com/r/ChatGPT/comments/13na8yp/highly_effective_prompt_for_summarizing_gpt4/ \n
            Title: Artificial intelligence\n
            Visited Date and Time : 2024-10-23T22:44:03-07:00 \n
            ============================DOCUMENT PAGE CONTENT CHUNK===================================== \n
            Page Content Chunk: \n\nArtificial intelligence (AI) has significantly transformed modern healthcare by enhancing diagnostic accuracy, personalizing patient care, and optimizing operational efficiency. AI algorithms can analyze vast datasets to identify patterns that may be missed by human practitioners, leading to improved diagnostic outcomes. \n\n
            ===================================================================================== \n
            
            =======================================DOCUMENT METADATA==================================== \n"
            Source: https://github.com/MODSetter/SurfSense \n
            Title: MODSetter/SurfSense: Personal AI Assistant for Internet Surfers and Researchers. \n
            Visited Date and Time : 2024-10-23T22:44:03-07:00 \n
            ============================DOCUMENT PAGE CONTENT CHUNK===================================== \n
            Page Content Chunk: \n\nAI systems have been deployed in radiology to detect anomalies in medical imaging with high precision,  reducing the risk of misdiagnosis and improving patient outcomes. Additionally, AI-powered chatbots and virtual assistants are being used to provide 24/7 support, answer queries, and offer personalized health advice\n\n
            ===================================================================================== \n
            
            =======================================DOCUMENT METADATA==================================== \n"
            Source: filename.pdf \n
            ============================DOCUMENT PAGE CONTENT CHUNK===================================== \n
            Page Content Chunk: \n\nApart from diagnostics, AI-driven tools facilitate personalized treatment plans by considering individual patient data, thereby improving patient outcomes\n\n
            ===================================================================================== \n
                    
        
        
        Ensure your response is structured something like this:
        ---
        **Answer:**
        Artificial intelligence (AI) has significantly transformed modern healthcare by enhancing diagnostic accuracy, personalizing patient care, and optimizing operational efficiency. AI algorithms can analyze vast datasets to identify patterns that may be missed by human practitioners, leading to improved diagnostic outcomes [1]. For instance, AI systems have been deployed in radiology to detect anomalies in medical imaging with high precision [2]. Moreover, AI-driven tools facilitate personalized treatment plans by considering individual patient data, thereby improving patient outcomes [3].

        **References:**
        1. (2024, October 23). [Artificial intelligence — GPT-4 Optimized: r/ChatGPT.](https://www.reddit.com/r/ChatGPT/comments/13na8yp/highly_effective_prompt_for_summarizing_gpt4/)  
        2. (2024, October 23). [MODSetter/SurfSense: Personal AI Assistant for Internet Surfers and Researchers.](https://github.com/MODSetter/SurfSense)
        3. (2024, October 23). filename.pdf  

        ---

        """
        
        local_report = asyncio.run(self.get_vectorstore_report(query=custom_prompt, report_type=report_type, report_source=report_source, documents=contextdocs))
        
        # web_report = asyncio.run(get_web_report(query=custom_prompt, report_type=report_type, report_source="web"))

        # structured_llm = self.llm.with_structured_output(AIAnswer)
        
        # out = structured_llm.invoke("Extract exact(i.e without changing) answer string and references information from : \n\n\n" + local_report)
        
        # mod_out = self.deduplicate_references_and_update_answer(answer=out.answer, references=out.references)
        
        return local_report
        