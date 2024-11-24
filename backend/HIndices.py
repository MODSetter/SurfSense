from datetime import datetime
import json
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
import numpy as np
from sqlalchemy.orm import Session
from fastapi import Depends, WebSocket

from prompts import report_prompt

import os
from dotenv import load_dotenv

from Utils.stringify import stringify
from pydmodels import AIAnswer, Reference
from database import SessionLocal
from models import Documents
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
 
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)       
        
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
        

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
                page_content=response.content,
                metadata=metadict
            )      
        
    def summarize_webpage_doc(self, page_no, doc, search_space):
        
        # Create an LLMChain for sub-query decomposition
        report_chain = report_prompt | self.llm
        
        
        if(IS_LOCAL_SETUP == True):
            response = report_chain.invoke({"document": doc})
            
            return Document(
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
         
    def encode_docs_hierarchical(self, documents, search_space_instance, files_type, db: Session = Depends(get_db)):
        """
        Creates and Saves/Updates docs in hierarchical indices and postgres table
        """
        page_no_offset = len(self.detailed_store.get()['documents'])    
        # Process documents
        summaries = []
        if(files_type=='WEBPAGE'):
            batch_summaries = [self.summarize_webpage_doc(page_no = i + page_no_offset, doc=doc, search_space=search_space_instance.name) for i, doc in enumerate(documents)]
        else:
            batch_summaries = [self.summarize_file_doc(page_no = i + page_no_offset , doc=doc, search_space=search_space_instance.name) for i, doc in enumerate(documents)]
            
      
        summaries.extend(batch_summaries)
        
        detailed_chunks = []
        
        for i, summary in enumerate(summaries):
            
            # Add single summary in vector store
            added_doc_id = self.summary_store.add_documents(filter_complex_metadata([summary]))
            
            if(files_type=='WEBPAGE'):
                new_pg_doc = Documents(
                    title=summary.metadata['VisitedWebPageTitle'],
                    document_metadata=stringify(summary.metadata),
                    page_content=documents[i].page_content,
                    file_type='WEBPAGE',
                    summary_vector_id=added_doc_id[0],
                )
            else:
                new_pg_doc = Documents(
                    title=summary.metadata['filename'],
                    document_metadata=stringify(summary.metadata),
                    page_content=documents[i].page_content,
                    file_type=summary.metadata['filetype'],
                    summary_vector_id=added_doc_id[0],
                )
            
            # Store it in PG
            search_space_instance.documents.append(new_pg_doc)
            db.commit()
            
            # Semantic chucking for better contexual compression
            text_splitter = SemanticChunker(embeddings=self.embeddings)
            chunks = text_splitter.split_documents([documents[i]])
            
            # Update metadata for detailed chunks
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
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
                
            detailed_chunks.extend(chunks)
            
        #update vector stores
        self.detailed_store.add_documents(filter_complex_metadata(detailed_chunks))

        return self.summary_store, self.detailed_store
    
    def delete_vector_stores(self, summary_ids_to_delete: list[str], db: Session = Depends(get_db)):
        self.summary_store.delete(ids=summary_ids_to_delete)       
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
                ref.source, Reference(id=str(len(unique_refs) + 1), title=ref.title, source=ref.source)
            ).id
            for ref in references
        }

        # Apply new mappings to the answer text
        updated_answer = answer
        for old_id, new_id in sorted(id_mapping.items(), key=lambda x: len(x[0]), reverse=True):
            updated_answer = updated_answer.replace(f'[{old_id}]', f'[{new_id}]')
        
        return updated_answer, list(unique_refs.values())

    async def ws_get_vectorstore_report(self, query: str, report_type: str, report_source: str, documents: List[Document],websocket: WebSocket) -> str:
        researcher = GPTResearcher(query=query, report_type=report_type, report_source=report_source, documents=documents, report_format="APA",websocket=websocket)
        await researcher.conduct_research()
        report = await researcher.write_report()
        return report

    async def ws_get_web_report(self, query: str, report_type: str, report_source: str, websocket: WebSocket) -> str:
        researcher = GPTResearcher(query=query, report_type=report_type, report_source=report_source, report_format="APA",websocket=websocket)
        await researcher.conduct_research()
        report = await researcher.write_report()
        return report

    async def ws_experimental_search(self, websocket: WebSocket, manager: ConnectionManager , query, search_space='GENERAL', report_type = "custom_report",  report_source = "langchain_documents"):
        custom_prompt = """
        Please answer the following user query using only the **Document Page Content** provided below, while citing sources exclusively from the **Document Metadata** section, in the format shown. **Do not add any external information.**

        **USER QUERY:** """ + query + """

        **Answer Requirements:**
        - Provide a detailed long response using IEEE-style in-text citations (e.g., [1], [2]) based solely on the **Document Page Content**.
        - Use **Document Metadata** only for citation details and format each reference exactly once, with no duplicates.
        - Structure references in this format at the end of your response, using this format: (Access Date and Time). [Title or Filename](Source)
        
        FOR EXAMPLE:
        EXAMPLE User Query : Explain the impact of artificial intelligence on modern healthcare.
        
        EXAMPLE Given Documents:
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
            Source: https://github.com/MODSetter/SurfSense \n
            Title: MODSetter/SurfSense: Personal AI Assistant for Internet Surfers and Researchers. \n
            Visited Date and Time : 2024-10-23T22:44:03-07:00 \n
            ============================DOCUMENT PAGE CONTENT CHUNK===================================== \n
            Page Content Chunk: \n\nAI algorithms can analyze a patient's genetic information to predict their risk of certain diseases and recommend tailored treatment plans. \n\n
            ===================================================================================== \n
            
            
            =======================================DOCUMENT METADATA==================================== \n"
            Source: filename.pdf \n
            ============================DOCUMENT PAGE CONTENT CHUNK===================================== \n
            Page Content Chunk: \n\nApart from diagnostics, AI-driven tools facilitate personalized treatment plans by considering individual patient data, thereby improving patient outcomes\n\n
            ===================================================================================== \n
                    
        
        
        Ensure your response is structured something like this:
        **OUTPUT FORMAT:**

        ---

        **Answer:**
        Artificial intelligence (AI) has significantly transformed modern healthcare by enhancing diagnostic accuracy, personalizing patient care, and optimizing operational efficiency. AI algorithms can analyze vast datasets to identify patterns that may be missed by human practitioners, leading to improved diagnostic outcomes [1]. For instance, AI systems have been deployed in radiology to detect anomalies in medical imaging with high precision [2]. Moreover, AI-driven tools facilitate personalized treatment plans by considering individual patient data, thereby improving patient outcomes [3].

        **References:**
        1. (2024, October 23). [Artificial intelligence — GPT-4 Optimized: r/ChatGPT](https://www.reddit.com/r/ChatGPT/comments/13na8yp/highly_effective_prompt_for_summarizing_gpt4)  
        2. (2024, October 23). [MODSetter/SurfSense: Personal AI Assistant for Internet Surfers and Researchers](https://github.com/MODSetter/SurfSense)
        3. (2024, October 23). [filename.pdf](filename.pdf)

        ---

        """
        
        structured_llm = self.llm.with_structured_output(AIAnswer)
        
        if report_source == "web" :
            if report_type == "custom_report" :
                ret_report = await self.ws_get_web_report(query=custom_prompt, report_type=report_type, report_source="web", websocket=websocket)
            else:
                ret_report = await self.ws_get_web_report(
                    query=query,
                    report_type=report_type, 
                    report_source="web", 
                    websocket=websocket
                )
                await manager.send_personal_message(
                        json.dumps({"type": "stream", "content": "Converting to IEEE format..."}),
                        websocket
                    )
                ret_report = self.llm.invoke("I have a report written in APA format. Please convert it to IEEE format, ensuring that all citations, references, headings, and overall formatting adhere to the IEEE style guidelines. Maintain the original content and structure while applying the correct IEEE formatting rules. Just return the converted report thats it. NOW MY REPORT : " + ret_report).content
                
             
         
                
            
            
            for chuck in structured_llm.stream(
                    "Please extract and separate the references from the main text. "
                    "References are formatted as follows:"
                    "[Reference Id]. (Access Date and Time). [Title or Filename](Source or URL). "
                    "Provide the text and references as distinct outputs. "
                    "IMPORTANT : Never hallucinate the references. If there is no reference just return nothing in the reference field."
                    "Here is the content to process: \n\n\n" + ret_report):
                # ans, sources = self.deduplicate_references_and_update_answer(answer=chuck.answer, references=chuck.references)
                
                await manager.send_personal_message(
                                json.dumps({"type": "stream", "sources": [source.model_dump() for source in chuck.references]}),
                                websocket
                            )
                    
                await manager.send_personal_message(
                        json.dumps({"type": "stream", "content": ret_report}),
                        websocket
                    )
            
            return 
        
        
        contextdocs = []
        top_summaries_compressor = FlashrankRerank(top_n=5)
        details_compressor = FlashrankRerank(top_n=50)
        top_summaries_retreiver = ContextualCompressionRetriever(
            base_compressor=top_summaries_compressor, base_retriever=self.summary_store.as_retriever(search_kwargs={'filter': {'search_space': search_space}})#
        )
        
        top_summaries_compressed_docs = top_summaries_retreiver.invoke(query)
        
        rel_docs = filter_complex_metadata(top_summaries_compressed_docs)
        
        await manager.send_personal_message(
                            json.dumps({"type": "stream", "relateddocs": [relateddoc.model_dump() for relateddoc in rel_docs]}, cls=NumpyEncoder),
                            websocket
                        )
        
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
            
            

        
        # local_report = asyncio.run(self.get_vectorstore_report(query=custom_prompt, report_type=report_type, report_source=report_source, documents=contextdocs))
        if report_source == "langchain_documents" :
            if report_type == "custom_report" :
                ret_report = await self.ws_get_vectorstore_report(query=custom_prompt, report_type=report_type, report_source=report_source, documents=contextdocs, websocket=websocket)
            else:
                ret_report = await self.ws_get_vectorstore_report(query=query, report_type=report_type, report_source=report_source, documents=contextdocs, websocket=websocket)
                await manager.send_personal_message(
                        json.dumps({"type": "stream", "content": "Converting to IEEE format..."}),
                        websocket
                    )
                ret_report = self.llm.invoke("I have a report written in APA format. Please convert it to IEEE format, ensuring that all citations, references, headings, and overall formatting adhere to the IEEE style guidelines. Maintain the original content and structure while applying the correct IEEE formatting rules. Just return the converted report thats it. NOW MY REPORT : " + ret_report).content
                
            
            for chuck in structured_llm.stream(
                    "Please extract and separate the references from the main text. "
                    "References are formatted as follows:"
                    "[Reference Id]. (Access Date and Time). [Title or Filename](Source or URL). "
                    "Provide the text and references as distinct outputs. "
                    "Ensure that in-text citation numbers such as [1], [2], (1), (2), etc., as well as in-text links or in-text citation links within the content, remain unaltered and are accurately extracted."
                    "IMPORTANT : Never hallucinate the references. If there is no reference just return nothing in the reference field."
                    "Here is the content to process: \n\n\n" + ret_report):
                ans, sources = self.deduplicate_references_and_update_answer(answer=chuck.answer, references=chuck.references)
                
                await manager.send_personal_message(
                                json.dumps({"type": "stream", "sources": [source.model_dump() for source in sources]}),
                                websocket
                            )
                    
                await manager.send_personal_message(
                        json.dumps({"type": "stream", "content": ans}),
                        websocket
                    )
                

        
            return 
        
        