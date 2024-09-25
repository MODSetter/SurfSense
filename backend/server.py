from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_ollama import OllamaLLM
from langchain_openai import ChatOpenAI
from prompts import CONTEXT_ANSWER_PROMPT, DATE_TODAY, SUBQUERY_DECOMPOSITION_PROMT
from pydmodels import ChatToUpdate, DescriptionResponse, DocWithContent, DocumentsToDelete, NewUserChat, UserCreate, UserQuery, RetrivedDocList, UserQueryResponse, UserQueryWithChatHistory
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Hierarchical Indices class
from HIndices import HIndices

from Utils.stringify import stringify

# Auth Libs
from fastapi import FastAPI, Depends, HTTPException, status
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

# Environment variables
IS_LOCAL_SETUP = os.environ.get("IS_LOCAL_SETUP")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES"))
ALGORITHM = os.environ.get("ALGORITHM")
API_SECRET_KEY = os.environ.get("API_SECRET_KEY")
SECRET_KEY = os.environ.get("SECRET_KEY")

app = FastAPI()

def get_db():
    """
    Dependency to get a database session.
    
    Yields:
        Session: A SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/chat/")
def get_user_query_response(data: UserQuery, response_model=UserQueryResponse):
    """
    Process a user query and return a response.
    
    Args:
        data (UserQuery): The user query data.
        
    Returns:
        UserQueryResponse: The response to the user query.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        query = data.query
        search_space = data.search_space
        
        # Initialize LLM based on setup
        if IS_LOCAL_SETUP == 'true':
            sub_query_llm = OllamaLLM(model="mistral-nemo", temperature=0)
            qa_llm = OllamaLLM(model="mistral-nemo", temperature=0)
        else:
            sub_query_llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini", api_key=data.openaikey)
            qa_llm = ChatOpenAI(temperature=0.5, model_name="gpt-4o-mini", api_key=data.openaikey)

        # Create an LLMChain for sub-query decomposition
        subquery_decomposer_chain = SUBQUERY_DECOMPOSITION_PROMT | sub_query_llm
        
        def decompose_query(original_query: str):
            """
            Decompose the original query into simpler sub-queries.
            
            Args:
                original_query (str): The original complex query
            
            Returns:
                List[str]: A list of simpler sub-queries
            """
            if IS_LOCAL_SETUP == 'true':
                response = subquery_decomposer_chain.invoke(original_query)
            else:
                response = subquery_decomposer_chain.invoke(original_query).content
                
            sub_queries = [q.strip() for q in response.split('\n') if q.strip() and not q.strip().startswith('Sub-queries:')]
            return sub_queries
        
        # Create Hierarchical Indices
        if IS_LOCAL_SETUP == 'true':
            index = HIndices(username=username)
        else:
            index = HIndices(username=username, api_key=data.openaikey) 
        
        # For those who want HyDE questions 
        # sub_queries = decompose_query(query)
        
        sub_queries = [query]

        duplicate_related_summary_docs = []
        context_to_answer = ""
        for sub_query in sub_queries:
            localreturn = index.local_search(query=sub_query, search_space=search_space)
            globalreturn, related_summary_docs = index.global_search(query=sub_query, search_space=search_space)
            
            context_to_answer += localreturn + "\n\n" + globalreturn

            duplicate_related_summary_docs.extend(related_summary_docs)
         
        # Remove duplicate documents
        combined_docs_seen_metadata = set()
        combined_docs_unique_documents = []

        for doc in duplicate_related_summary_docs:
            doc.metadata['relevance_score'] = 0.0
            metadata_tuple = tuple(sorted(doc.metadata.items()))
            if metadata_tuple not in combined_docs_seen_metadata:
                combined_docs_seen_metadata.add(metadata_tuple)
                combined_docs_unique_documents.append(doc)
                
        returnDocs = []
        for doc in combined_docs_unique_documents:
            entry = DocWithContent(
                BrowsingSessionId=doc.metadata['BrowsingSessionId'],
                VisitedWebPageURL=doc.metadata['VisitedWebPageURL'],
                VisitedWebPageContent=doc.page_content,
                VisitedWebPageTitle=doc.metadata['VisitedWebPageTitle'],
                VisitedWebPageDateWithTimeInISOString=doc.metadata['VisitedWebPageDateWithTimeInISOString'],
                VisitedWebPageReffererURL=doc.metadata['VisitedWebPageReffererURL'],
                VisitedWebPageVisitDurationInMilliseconds=doc.metadata['VisitedWebPageVisitDurationInMilliseconds'],
            )
            
            returnDocs.append(entry)
        
        # Generate final answer
        ans_chain = CONTEXT_ANSWER_PROMPT | qa_llm
        finalans = ans_chain.invoke({"query": query, "context": context_to_answer})
        
        if IS_LOCAL_SETUP == 'true':
            return UserQueryResponse(response=finalans, relateddocs=returnDocs)
        else:
            return UserQueryResponse(response=finalans.content, relateddocs=returnDocs)
    
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
@app.post("/save/")
def save_data(apires: RetrivedDocList, db: Session = Depends(get_db)):
    """
    Save retrieved documents to the database and vector stores.
    
    Args:
        apires (RetrivedDocList): The list of documents to save.
        db (Session): The database session.
        
    Returns:
        dict: A message indicating the success of the operation.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(apires.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        print("STARTED")
        
        DocumentPgEntry = []
        raw_documents = []
        searchspace = db.query(SearchSpace).filter(SearchSpace.search_space == apires.search_space).first()
        
        for doc in apires.documents:
            content = f"USER BROWSING SESSION EVENT: \n"
            content += f"=======================================METADATA==================================== \n"
            content += f"User Browsing Session ID : {doc.metadata.BrowsingSessionId} \n"
            content += f"User Visited website with url : {doc.metadata.VisitedWebPageURL} \n"
            content += f"This visited website url had title : {doc.metadata.VisitedWebPageTitle} \n"
            content += f"User Visited this website from reffering url : {doc.metadata.VisitedWebPageReffererURL} \n"
            content += f"User Visited this website url at this Date and Time : {doc.metadata.VisitedWebPageDateWithTimeInISOString} \n"
            content += f"User Visited this website for : {str(doc.metadata.VisitedWebPageVisitDurationInMilliseconds)} milliseconds. \n"
            content += f"===================================================================================== \n"
            content += f"Webpage Content of the visited webpage url in markdown format : \n\n {doc.pageContent} \n\n"
            content += f"===================================================================================== \n"
            raw_documents.append(Document(page_content=content, metadata=doc.metadata.__dict__))
            
            pgdocmeta = stringify(doc.metadata.__dict__)

            if searchspace:
                DocumentPgEntry.append(Documents(file_type='WEBPAGE', title=doc.metadata.VisitedWebPageTitle, search_space=searchspace, document_metadata=pgdocmeta, page_content=content))
            else:
                DocumentPgEntry.append(Documents(file_type='WEBPAGE', title=doc.metadata.VisitedWebPageTitle, search_space=SearchSpace(search_space=apires.search_space.upper()), document_metadata=pgdocmeta, page_content=content))
            
        # Save docs in PG
        user = db.query(User).filter(User.username == username).first()
        user.documents.extend(DocumentPgEntry)
        
        db.commit()   
        
        # Create Hierarchical Indices
        if IS_LOCAL_SETUP == 'true':
            index = HIndices(username=username)
        else:
            index = HIndices(username=username, api_key=apires.openaikey)    
        
        # Save Indices in vector stores
        index.encode_docs_hierarchical(documents=raw_documents, files_type='WEBPAGE', search_space=apires.search_space.upper(), db=db)
        
        print("FINISHED")
        
        return {
            "success": "Graph Will be populated Shortly"
        }
        
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

@app.post("/chat/docs")
def doc_chat_with_history(data: UserQueryWithChatHistory, response_model=DescriptionResponse):
    """
    Process a user query with chat history and return a response.
    
    Args:
        data (UserQueryWithChatHistory): The user query data with chat history.
        
    Returns:
        DescriptionResponse: The response to the user query.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        if IS_LOCAL_SETUP == 'true':
            llm = OllamaLLM(model="mistral-nemo", temperature=0)
        else:
            llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini", api_key=data.openaikey)
        
        chatHistory = []
        
        for chat in data.chat:
            if chat.type == 'system':
                chatHistory.append(SystemMessage(content=DATE_TODAY + """You are a helpful assistant for question-answering tasks.
        Use the following pieces of retrieved context to answer the question.
        If you don't know the answer, just say that you don't know. 
        Context:""" + str(chat.content)))
                
            if chat.type == 'ai':
                chatHistory.append(AIMessage(content=chat.content))
                
            if chat.type == 'human':
                chatHistory.append(HumanMessage(content=chat.content))
                
        chatHistory.append(("human", "{input}"))
        
        qa_prompt = ChatPromptTemplate.from_messages(chatHistory)
            
        descriptionchain = qa_prompt | llm
            
        response = descriptionchain.invoke({"input": data.query})
        
        if IS_LOCAL_SETUP == 'true':
            return DescriptionResponse(response=response)
        else:
            return DescriptionResponse(response=response.content)
            
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

@app.post("/delete/docs")
def delete_all_related_data(data: DocumentsToDelete, db: Session = Depends(get_db)):
    """
    Delete documents and related data.
    
    Args:
        data (DocumentsToDelete): The data containing documents to delete.
        db (Session): The database session.
        
    Returns:
        dict: A message indicating the result of the deletion.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        if IS_LOCAL_SETUP == 'true':
            index = HIndices(username=username)
        else:
            index = HIndices(username=username, api_key=data.openaikey)
            
        message = index.delete_vector_stores(summary_ids_to_delete=data.ids_to_delete, db=db)
        
        return {
            "message": message
        }
            
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")

# AUTH CODE
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_username(db: Session, username: str):
    """
    Retrieve a user by username from the database.
    
    Args:
        db (Session): The database session.
        username (str): The username to search for.
        
    Returns:
        User: The user object if found, None otherwise.
    """
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate):
    """
    Create a new user in the database.
    
    Args:
        db (Session): The database session.
        user (UserCreate): The user data to create.
        
    Returns:
        str: A message indicating the completion of user creation.
    """
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    return "complete"

@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    
    Args:
        user (UserCreate): The user data for registration.
        db (Session): The database session.
        
    Returns:
        str: A message indicating the completion of user registration.
        
    Raises:
        HTTPException: If the API secret key is invalid or the username is already registered.
    """
    if user.apisecretkey != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    del user.apisecretkey
    return create_user(db=db, user=user)

def authenticate_user(username: str, password: str, db: Session):
    """
    Authenticate a user.
    
    Args:
        username (str): The username of the user.
        password (str): The password of the user.
        db (Session): The database session.
        
    Returns:
        User: The authenticated user object if successful, False otherwise.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not pwd_context.verify(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Create an access token.
    
    Args:
        data (dict): The data to encode in the token.
        expires_delta (timedelta, optional): The expiration time for the token.
        
    Returns:
        str: The encoded JWT token.
    """
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
    """
    Authenticate a user and return an access token.
    
    Args:
        form_data (OAuth2PasswordRequestForm): The form data containing username and password.
        db (Session): The database session.
        
    Returns:
        dict: A dictionary containing the access token and token type.
        
    Raises:
        HTTPException: If the username or password is incorrect.
    """
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
    """
    Verify the validity of a token.
    
    Args:
        token (str): The token to verify.
        
    Returns:
        dict: The payload of the token if valid.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
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
    """
    Verify a user token.
    
    Args:
        token (str): The token to verify.
        
    Returns:
        dict: A message indicating the validity of the token.
    """
    verify_token(token=token)
    return {"message": "Token is valid"}

@app.post("/user/chat/save")
def populate_user_chat(chat: NewUserChat, db: Session = Depends(get_db)):
    """
    Save a new chat for a user.
    
    Args:
        chat (NewUserChat): The chat data to save.
        db (Session): The database session.
        
    Returns:
        dict: A message indicating the success of the operation.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
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
    """
    Update an existing chat for a user.
    
    Args:
        chat (ChatToUpdate): The chat data to update.
        db (Session): The database session.
        
    Returns:
        dict: A message indicating the success of the operation.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
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
    """
    Delete a chat for a user.
    
    Args:
        token (str): The user's authentication token.
        chatid (str): The ID of the chat to delete.
        db (Session): The database session.
        
    Returns:
        dict: A message indicating the success of the operation.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
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
    
@app.get("/user/{token}")
async def get_user_with_token(token: str, db: Session = Depends(get_db)):
    """
    Get user information using a token.
    
    Args:
        token (str): The user's authentication token.
        db (Session): The database session.
        
    Returns:
        dict: User information including ID, username, chats, and documents.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
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
    """
    Get all search spaces.
    
    Args:
        token (str): The user's authentication token.
        db (Session): The database session.
        
    Returns:
        dict: A dictionary containing all search spaces.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
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
