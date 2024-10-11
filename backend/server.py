from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from sqlalchemy import insert
from prompts import CONTEXT_ANSWER_PROMPT, DATE_TODAY, SUBQUERY_DECOMPOSITION_PROMT
from pydmodels import ChatToUpdate, DescriptionResponse, DocWithContent, DocumentsToDelete, NewUserChat, UserCreate, UserQuery, RetrivedDocList, UserQueryResponse, UserQueryWithChatHistory
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_unstructured import UnstructuredLoader

#Heirerical Indices class
from HIndices import HIndices

from Utils.stringify import stringify

# Auth Libs
from fastapi import FastAPI, Depends, Form, HTTPException, status, UploadFile
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from models import Chat, Documents, SearchSpace, User
from database import SessionLocal
from fastapi.middleware.cors import CORSMiddleware


import os
from dotenv import load_dotenv
load_dotenv()

IS_LOCAL_SETUP = os.environ.get("IS_LOCAL_SETUP")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES"))
ALGORITHM = os.environ.get("ALGORITHM")
API_SECRET_KEY = os.environ.get("API_SECRET_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")
UNSTRUCTURED_API_KEY = os.environ.get("UNSTRUCTURED_API_KEY")

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
        
@app.post("/uploadfiles/")
async def upload_files(files: list[UploadFile], token: str = Depends(oauth2_scheme), search_space: str = Form(...), api_key: str = Form(...), db: Session = Depends(get_db)):
    try:
        # Decode and verify the token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
    
        docs = []
        
        for file in files:
            
            loader = UnstructuredLoader(
                    file=file.file, 
                    api_key=UNSTRUCTURED_API_KEY,
                    partition_via_api=True,
                    chunking_strategy="basic",
                    max_characters=90000,
                    include_orig_elements=False,
                )

            filedocs = loader.load()
            
            fileswithfilename = []
            for f in filedocs:
                temp = f
                temp.metadata['filename'] = file.filename
                fileswithfilename.append(temp)
            
            docs.extend(fileswithfilename)
        
        # Initialize containers for documents and entries
        DocumentPgEntry = []
        raw_documents = []
        
        # Fetch the search space from the database or create it if it doesn't exist
        searchspace = db.query(SearchSpace).filter(SearchSpace.search_space == search_space.upper()).first()
        if not searchspace:
            stmt = insert(SearchSpace).values(search_space=search_space.upper())
            db.execute(stmt)
            db.commit()
        
        # Process each document in the retrieved document list
        for doc in docs:

            raw_documents.append(Document(page_content=doc.page_content, metadata=doc.metadata))
            
            # Stringify the document metadata
            pgdocmeta = stringify(doc.metadata)
            
            DocumentPgEntry.append(Documents(
                file_type=doc.metadata['filetype'],
                title=doc.metadata['filename'],
                search_space=db.query(SearchSpace).filter(SearchSpace.search_space == search_space.upper()).first(),
                document_metadata=pgdocmeta,
                page_content=doc.page_content
            ))

        
        # Save documents in PostgreSQL
        user = db.query(User).filter(User.username == username).first()
        user.documents.extend(DocumentPgEntry)
        db.commit()   
        
        # Create hierarchical indices
        if IS_LOCAL_SETUP == 'true':
            index = HIndices(username=username)
        else:
            index = HIndices(username=username, api_key=api_key)    
        
        # Save indices in vector stores
        index.encode_docs_hierarchical(documents=raw_documents, files_type='OTHER', search_space=search_space.upper(), db=db)
        
        print("FINISHED")
        
        return {
            "message": "Files Uploaded Successfully"
        }

    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

@app.post("/chat/")
def get_user_query_response(data: UserQuery, response_model=UserQueryResponse):
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        query = data.query
        search_space = data.search_space
        
        if(IS_LOCAL_SETUP == 'true'):
            sub_query_llm = OllamaLLM(model="mistral-nemo",temperature=0)
            qa_llm = OllamaLLM(model="mistral-nemo",temperature=0)
        else:
            sub_query_llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini", api_key=data.openaikey)
            qa_llm = ChatOpenAI(temperature=0.5, model_name="gpt-4o-mini", api_key=data.openaikey)



        # Create an LLMChain for sub-query decomposition
        subquery_decomposer_chain = SUBQUERY_DECOMPOSITION_PROMT | sub_query_llm
        
        #Experimental
        def decompose_query(original_query: str):
            """
            Decompose the original query into simpler sub-queries.
            
            Args:
            original_query (str): The original complex query
            
            Returns:
            List[str]: A list of simpler sub-queries
            """
            if(IS_LOCAL_SETUP == 'true'):
                response = subquery_decomposer_chain.invoke(original_query)
            else:
                response = subquery_decomposer_chain.invoke(original_query).content
                
            sub_queries = [q.strip() for q in response.split('\n') if q.strip() and not q.strip().startswith('Sub-queries:')]
            return sub_queries
        
        
        # Create Heirarical Indecices
        if(IS_LOCAL_SETUP == 'true'):
            index = HIndices(username=username)
        else:
            index = HIndices(username=username,api_key=data.openaikey) 
            
           
        
        # For Those Who Want HyDe Questions 
        # sub_queries = decompose_query(query)
        
        sub_queries = []
        sub_queries.append(query)

        duplicate_related_summary_docs = []
        context_to_answer = ""
        for sub_query in sub_queries:
            localreturn = index.local_search(query=sub_query, search_space=search_space)
            globalreturn, related_summary_docs = index.global_search(query=sub_query, search_space=search_space)
            
            context_to_answer += localreturn + "\n\n" + globalreturn

            duplicate_related_summary_docs.extend(related_summary_docs)
         
            
        combined_docs_seen_metadata = set()
        combined_docs_unique_documents = []

        for doc in duplicate_related_summary_docs:
            # Convert metadata to a tuple of its items (this allows it to be added to a set)
            doc.metadata['relevance_score'] = 0.0
            metadata_tuple = tuple(sorted(doc.metadata.items()))
            if metadata_tuple not in combined_docs_seen_metadata:
                combined_docs_seen_metadata.add(metadata_tuple)
                combined_docs_unique_documents.append(doc)
                
        returnDocs = []
        for doc in combined_docs_unique_documents:
            entry = DocWithContent(
                DocMetadata=stringify(doc.metadata),
                Content=doc.page_content
            )
            
            returnDocs.append(entry)
        
           
        ans_chain = CONTEXT_ANSWER_PROMPT | qa_llm
        
        finalans = ans_chain.invoke({"query": query, "context": context_to_answer})
        
        
        if(IS_LOCAL_SETUP == 'true'):
            return UserQueryResponse(response=finalans, relateddocs=returnDocs)
        else:
            return UserQueryResponse(response=finalans.content, relateddocs=returnDocs)
    
    
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
# SAVE DOCS
@app.post("/save/")
def save_data(apires: RetrivedDocList, db: Session = Depends(get_db)):
    """
    Save retrieved documents to the database and encode them for hierarchical indexing.

    This endpoint processes the provided documents, saves related information
    in the PostgreSQL database, and updates hierarchical indices for the user.
    Args:
        apires (RetrivedDocList): The list of retrieved documents with metadata.
        db (Session, optional): Dependency-injected session for database operations.

    Returns:
        dict: A message indicating the success of the operation.
    
    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        # Decode token and extract username
        payload = jwt.decode(apires.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        print("STARTED")
        
        # Initialize containers for documents and entries
        DocumentPgEntry = []
        raw_documents = []
        
        # Fetch the search space from the database
        searchspace = db.query(SearchSpace).filter(SearchSpace.search_space == apires.search_space.upper()).first()
        if not searchspace:
            stmt = insert(SearchSpace).values(search_space=apires.search_space.upper())
            db.execute(stmt)
            db.commit()
        
        # Process each document in the retrieved document list
        for doc in apires.documents:
            # Construct document content
            content = (
                f"USER BROWSING SESSION EVENT: \n"
                f"=======================================METADATA==================================== \n"
                f"User Browsing Session ID : {doc.metadata.BrowsingSessionId} \n"
                f"User Visited website with url : {doc.metadata.VisitedWebPageURL} \n"
                f"This visited website url had title : {doc.metadata.VisitedWebPageTitle} \n"
                f"User Visited this website from referring url : {doc.metadata.VisitedWebPageReffererURL} \n"
                f"User Visited this website url at this Date and Time : {doc.metadata.VisitedWebPageDateWithTimeInISOString} \n"
                f"User Visited this website for : {str(doc.metadata.VisitedWebPageVisitDurationInMilliseconds)} milliseconds. \n"
                f"===================================================================================== \n"
                f"Webpage Content of the visited webpage url in markdown format : \n\n{doc.pageContent}\n\n"
                f"===================================================================================== \n"
            )
            raw_documents.append(Document(page_content=content, metadata=doc.metadata.__dict__))
            
            # Stringify the document metadata
            pgdocmeta = stringify(doc.metadata.__dict__)
            
            DocumentPgEntry.append(Documents(
                file_type='WEBPAGE',
                title=doc.metadata.VisitedWebPageTitle,
                search_space=searchspace,
                document_metadata=pgdocmeta,
                page_content=content
            ))
        
        # Save documents in PostgreSQL
        user = db.query(User).filter(User.username == username).first()
        user.documents.extend(DocumentPgEntry)
        db.commit()   
        
        # Create hierarchical indices
        if IS_LOCAL_SETUP == 'true':
            index = HIndices(username=username)
        else:
            index = HIndices(username=username, api_key=apires.openaikey)    
        
        # Save indices in vector stores
        index.encode_docs_hierarchical(documents=raw_documents, files_type='WEBPAGE', search_space=apires.search_space.upper(), db=db)
        
        print("FINISHED")
        
        return {
            "success": "Graph Will be populated Shortly"
        }
        
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")
     
# Multi DOC Chat
@app.post("/chat/docs")
def doc_chat_with_history(data: UserQueryWithChatHistory, response_model=DescriptionResponse):
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        if(IS_LOCAL_SETUP == 'true'):
            llm = OllamaLLM(model="mistral-nemo",temperature=0)
        else:
            llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini", api_key=data.openaikey)
        
        chatHistory = []
        
        for chat in data.chat:
            if(chat.type == 'system'):
                chatHistory.append(SystemMessage(content=DATE_TODAY + """You are an helpful assistant for question-answering tasks.
        Use the following pieces of retrieved context to answer the question.
        If you don't know the answer, just say that you don't know. 
        Context:""" + str(chat.content)))
                
            if(chat.type == 'ai'):
                chatHistory.append(AIMessage(content=chat.content))
                
            if(chat.type == 'human'):
                chatHistory.append(HumanMessage(content=chat.content))
                
        chatHistory.append(("human", "{input}"));
        

        qa_prompt = ChatPromptTemplate.from_messages(chatHistory)
            
        descriptionchain = qa_prompt | llm
            
        response = descriptionchain.invoke({"input": data.query})
        
        if(IS_LOCAL_SETUP == 'true'):
            return DescriptionResponse(response=response)
        else:
            return DescriptionResponse(response=response.content)
            
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")


 # Multi DOC Chat

@app.post("/delete/docs")
def delete_all_related_data(data: DocumentsToDelete, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        if(IS_LOCAL_SETUP == 'true'):
            index = HIndices(username=username)
        else:
            index = HIndices(username=username,api_key=data.openaikey)
            
        message = index.delete_vector_stores(summary_ids_to_delete=data.ids_to_delete,db=db )
        
        return {
            "message": message
        }
            
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")




# Manual Origins
# origins = [
#     "http://localhost:3000",  # Adjust the port if your frontend runs on a different one
#     "https://yourfrontenddomain.com",
# ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins from the list
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    return "complete"

@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    if(user.apisecretkey != API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    del user.apisecretkey
    return create_user(db=db, user=user)

# Authenticate the user
def authenticate_user(username: str, password: str, db: Session):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user

# Create access token
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

@app.get("/verify-token/{token}")
async def verify_user_token(token: str):
    verify_token(token=token)
    return {"message": "Token is valid"}

@app.post("/user/chat/save")
def populate_user_chat(chat: NewUserChat, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(chat.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        user = db.query(User).filter(User.username == username).first()
        newchat = Chat(type=chat.type, title=chat.title, chats_list=chat.chats_list)
        
        user.chats.append(newchat)
        db.commit()
        return {
            "message": "Chat Saved"
        }
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

@app.post("/user/chat/update")
def populate_user_chat(chat: ChatToUpdate, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(chat.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        chatindb = db.query(Chat).filter(Chat.id == chat.chatid).first()
        chatindb.chats_list = chat.chats_list
        
        db.commit()
        return {
            "message": "Chat Updated"
        }
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

@app.get("/user/chat/delete/{token}/{chatid}")
async def delete_chat_of_user(token: str, chatid: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        chatindb = db.query(Chat).filter(Chat.id == chatid).first()
        db.delete(chatindb)
        db.commit()
        return {
            "message": "Chat Deleted"
        }
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")
    
#Gets user id & name
@app.get("/user/{token}")
async def get_user_with_token(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        user = db.query(User).filter(User.username == username).first()
        return {
            "userid": user.id,
            "username": user.username,
            "chats": user.chats,
            "documents": user.documents
        }
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

@app.get("/searchspaces/{token}")
async def get_user_with_token(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        search_spaces = db.query(SearchSpace).all()
        return {
            "search_spaces": search_spaces
        }
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

    

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
    
    
    
