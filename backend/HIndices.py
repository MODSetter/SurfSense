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

from database import SessionLocal
from models import Documents, User
from prompts import CONTEXT_ANSWER_PROMPT
load_dotenv()

IS_LOCAL_SETUP = os.environ.get("IS_LOCAL_SETUP")

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
        if(IS_LOCAL_SETUP == 'true'):
            self.llm = OllamaLLM(model="mistral-nemo",temperature=0)
            self.embeddings = OllamaEmbeddings(model="mistral-nemo")
        else:
            self.llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini", api_key=api_key)
            self.embeddings = OpenAIEmbeddings(api_key=api_key)
            
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

        report_template = """You are a forensic investigator expert in making detailed report of the document. You are given the document make a report of it.

        DOCUMENT: {document}
        
        Detailed Report:"""


        report_prompt = PromptTemplate(
            input_variables=["document"],
            template=report_template
        )
        
        # Create an LLMChain for sub-query decomposition
        report_chain = report_prompt | self.llm
        
        
        if(IS_LOCAL_SETUP == 'true'):
            # Local LLMS suck at summaries so need this slow and painful procedure
            text_splitter = SemanticChunker(embeddings=self.embeddings)
            chunks = text_splitter.split_documents([doc]) 
            combined_summary = ""
            for i, chunk in enumerate(chunks):
                print("GENERATING SUMMARY FOR CHUNK "+ str(i))
                chunk_summary = report_chain.invoke({"document": chunk})
                combined_summary += "\n\n" + chunk_summary +  "\n\n"
                
            response = combined_summary
            
                            
            metadict = {
                    "page": page_no, 
                    "summary": True,
                    "search_space": search_space,
                    }
            
            # metadict['languages'] = metadict['languages'][0]
            
            metadict.update(doc.metadata)
            
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

        
        report_template = """You are a forensic investigator expert in making detailed report of the document. You are given the document make a report of it.

        DOCUMENT: {document}
        
        Detailed Report:"""


        report_prompt = PromptTemplate(
            input_variables=["document"],
            template=report_template
        )
        
        # Create an LLMChain for sub-query decomposition
        report_chain = report_prompt | self.llm
        
        
        if(IS_LOCAL_SETUP == 'true'):
            # Local LLMS suck at summaries so need this slow and painful procedure
            text_splitter = SemanticChunker(embeddings=self.embeddings)
            chunks = text_splitter.split_documents([doc]) 
            combined_summary = ""
            for i, chunk in enumerate(chunks):
                print("GENERATING SUMMARY FOR CHUNK "+ str(i))
                chunk_summary = report_chain.invoke({"document": chunk})
                combined_summary += "\n\n" + chunk_summary +  "\n\n"
                
            response = combined_summary
            
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
        

        # DocumentPgEntry = []   
        # searchspace = db.query(SearchSpace).filter(SearchSpace.search_space == search_space).first()
        
        # for doc in documents:
        #     pgdocmeta = stringify(doc.metadata)

        #     if(searchspace):
        #         DocumentPgEntry.append(Documents(file_type='WEBPAGE',title=doc.metadata.VisitedWebPageTitle,search_space=search_space, document_metadata=pgdocmeta, page_content=doc.page_content))
        #     else:
        #         DocumentPgEntry.append(Documents(file_type='WEBPAGE',title=doc.metadata.VisitedWebPageTitle,search_space=SearchSpace(search_space=search_space), document_metadata=pgdocmeta, page_content=doc.page_content))
        

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
            
        # batch_summaries = [summarize_doc(i + summary_last_id, doc) for i, doc in enumerate(documents)]
        summaries.extend(batch_summaries)
        
        detailed_chunks = []
        
        for i, summary in enumerate(summaries):
            
            # Semantic chucking for better contexual comprression
            text_splitter = SemanticChunker(embeddings=self.embeddings)
            chunks = text_splitter.split_documents([documents[i]])
            
            user.documents[-(len(summaries) - i)].desc_vector_start = detail_id_counter
            user.documents[-(len(summaries) - i)].desc_vector_end = detail_id_counter + len(chunks)
            # summary_entry = db.query(Documents).filter(Documents.id == int(user.documents[-1].id)).first()
            # summary_entry.desc_vector_start = detail_id_counter
            # summary_entry.desc_vector_end = detail_id_counter + len(chunks)
            
            db.commit()

            # Update metadata for detailed chunks
            for i, chunk in enumerate(chunks):
                chunk.id = str(detail_id_counter)
                chunk.metadata.update({
                    "chunk_id": detail_id_counter,
                    "summary": False,
                    "page": summary.metadata['page'],
                })
                
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
                       
    def is_query_answerable(self, query, context):
        prompt = PromptTemplate(
            template="""You are a grader assessing relevance of a retrieved document to a user question. \n 
            Here is the retrieved document: \n\n {context} \n\n
            Here is the user question: {question} \n
            If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. \n
            Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.
            Only return 'yes' or 'no'""",
            input_variables=["context", "question"],
        )
        
        ans_chain = prompt | self.llm
        
        finalans = ans_chain.invoke({"question": query, "context": context})
        
        if(IS_LOCAL_SETUP == 'true'):
            return finalans
        else:
            return finalans.content
         
    def local_search(self, query, search_space='GENERAL'):
        top_summaries_compressor = FlashrankRerank(top_n=5)
        details_compressor = FlashrankRerank(top_n=30)
        top_summaries_retreiver = ContextualCompressionRetriever(
            base_compressor=top_summaries_compressor, base_retriever=self.summary_store.as_retriever(search_kwargs={'filter': {'search_space': search_space}})
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
            
            contextdocs = top_summaries_compressed_docs + detailed_compressed_docs
            
            context_to_answer = ""
            for i, doc in enumerate(contextdocs):
                content = f":DOCUMENT {str(i)}\n"
                content += f"=======================================METADATA==================================== \n"
                content += f"Webpage Url : {doc.metadata['VisitedWebPageURL']} \n"
                content += f"Webpage Title : {doc.metadata['VisitedWebPageTitle']} \n"
                content += f"Accessed on (Date With Time In ISO String): {doc.metadata['VisitedWebPageDateWithTimeInISOString']} \n"
                content += f"===================================================================================== \n"
                content += f"Webpage CONTENT CHUCK: \n\n {doc.page_content} \n\n"
                content += f"===================================================================================== \n"
                
                context_to_answer += content
                
                content = ""
                
            if(self.is_query_answerable(query=query, context=context_to_answer).lower() == 'yes'):
                ans_chain = CONTEXT_ANSWER_PROMPT | self.llm
        
                finalans = ans_chain.invoke({"query": query, "context": context_to_answer})
                
                if(IS_LOCAL_SETUP == 'true'):
                    return finalans
                else:
                    return finalans.content
            else:
                continue
            
        return "I couldn't find any answer"
        
    def global_search(self,query, search_space='GENERAL'):
        top_summaries_compressor = FlashrankRerank(top_n=20)
        
        top_summaries_retreiver = ContextualCompressionRetriever(
            base_compressor=top_summaries_compressor, base_retriever=self.summary_store.as_retriever(search_kwargs={'filter': {'search_space': search_space}})
        )
        
        top_summaries_compressed_docs = top_summaries_retreiver.invoke(query)
        
        context_to_answer = ""
        for i, doc in enumerate(top_summaries_compressed_docs):
            content = f":DOCUMENT {str(i)}\n"
            content += f"=======================================METADATA==================================== \n"
            content += f"Webpage Url : {doc.metadata['VisitedWebPageURL']} \n"
            content += f"Webpage Title : {doc.metadata['VisitedWebPageTitle']} \n"
            content += f"Accessed on (Date With Time In ISO String): {doc.metadata['VisitedWebPageDateWithTimeInISOString']} \n"
            content += f"===================================================================================== \n"
            content += f"Webpage CONTENT CHUCK: \n\n {doc.page_content} \n\n"
            content += f"===================================================================================== \n"
            
            context_to_answer += content
                
        ans_chain = CONTEXT_ANSWER_PROMPT | self.llm
        
        finalans = ans_chain.invoke({"query": query, "context": context_to_answer})
        
        if(IS_LOCAL_SETUP == 'true'):
            return finalans, top_summaries_compressed_docs
        else:
            return finalans.content, top_summaries_compressed_docs
        
