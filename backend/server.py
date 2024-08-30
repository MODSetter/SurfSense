from __future__ import annotations

from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from envs import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, API_SECRET_KEY, SECRET_KEY
from prompts import CYPHER_QA_PROMPT, DATE_TODAY, DOC_DESCRIPTION_PROMPT, GRAPH_QUERY_GEN_PROMPT, NOTIFICATION_GENERATION_PROMT, SIMILARITY_SEARCH_PROMPT , CYPHER_GENERATION_PROMPT, DOCUMENT_METADATA_EXTRACTION_PROMT
from pydmodels import ChatToUpdate, DescriptionResponse, GraphDocs, NewUserChat, NewUserData, Notifications, PrecisionQuery, PrecisionResponse, UserQuery, DocMeta, RetrivedDocList, UserQueryResponse, UserQueryWithChatHistory, VectorSearchQuery
from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

#Our Imps
from LLMGraphTransformer import LLMGraphTransformer
from langchain_openai import ChatOpenAI
from DataExample import examples
# import nest_asyncio
# from langchain_community.chains.graph_qa.gremlin import GremlinQAChain
# from langchain_community.graphs import GremlinGraph
# from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
# from langchain_core.documents import Document
# from langchain_openai import AzureChatOpenAI

# Auth Libs
from fastapi import FastAPI, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from models import Chat, Notification, User
from database import SessionLocal, engine
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import AzureChatOpenAI


app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
class UserCreate(BaseModel):
    username: str
    password: str
    apisecretkey: str


  
# General GraphCypherQAChain
@app.post("/")
def get_user_query_response(data: UserQuery, response_model=UserQueryResponse):
    
    if(data.apisecretkey != API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    
    graph = Neo4jGraph(url=data.neourl, username=data.neouser, password=data.neopass)
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=None,
        timeout=None,
        api_key=data.openaikey
    )
    
    # Query Expansion
    # searchchain = GRAPH_QUERY_GEN_PROMPT | llm
        
    # qry = searchchain.invoke({"question": data.query, "context": examples})
    
    query = data.query #qry.content
    
    embeddings = OpenAIEmbeddings(
        model="text-embedding-ada-002",
        api_key=data.openaikey,
    )

    
    chain = GraphCypherQAChain.from_llm(
        graph=graph, 
        cypher_prompt=CYPHER_GENERATION_PROMPT, 
        cypher_llm=llm, 
        verbose=True, 
        validate_cypher=True, 
        qa_prompt=CYPHER_QA_PROMPT ,
        qa_llm=llm,
        return_intermediate_steps=True,
        top_k=5,
    )
    
    vector_index = Neo4jVector.from_existing_graph(
        embeddings,
        graph=graph,
        search_type="hybrid",
        node_label="Document",
        text_node_properties=["text"],
        embedding_node_property="embedding",
    )
    
    graphdocs = vector_index.similarity_search(data.query,k=15)
    docsDict = {}
    
    for d in graphdocs:
        if d.metadata['BrowsingSessionId'] not in docsDict:
            newVal = d.metadata.copy()
            newVal['VisitedWebPageContent'] = d.page_content
            docsDict[d.metadata['BrowsingSessionId']] = newVal
        else:
            docsDict[d.metadata['BrowsingSessionId']]['VisitedWebPageContent'] += d.page_content
            
    docstoreturn = []
    
    for x in docsDict.values():
        docstoreturn.append(DocMeta(
            BrowsingSessionId=x['BrowsingSessionId'],
            VisitedWebPageURL=x['VisitedWebPageURL'],
            VisitedWebPageVisitDurationInMilliseconds=x['VisitedWebPageVisitDurationInMilliseconds'],
            VisitedWebPageTitle=x['VisitedWebPageTitle'],
            VisitedWebPageReffererURL=x['VisitedWebPageReffererURL'],
            VisitedWebPageDateWithTimeInISOString=x['VisitedWebPageDateWithTimeInISOString'],
            VisitedWebPageContent=x['VisitedWebPageContent']
        ))
 

    try:
        responsegrp = chain.invoke({"query": query})
           
        if "don't know" in responsegrp["result"]:
            raise Exception("No response from graph")
        
        structured_llm = llm.with_structured_output(VectorSearchQuery)
        doc_extract_chain = DOCUMENT_METADATA_EXTRACTION_PROMT | structured_llm
        
        newquery = doc_extract_chain.invoke(responsegrp["intermediate_steps"][1]["context"])
        
        graphdocs = vector_index.similarity_search(newquery.searchquery,k=15)
    
        docsDict = {}
        
        for d in graphdocs:
            if d.metadata['BrowsingSessionId'] not in docsDict:
                newVal = d.metadata.copy()
                newVal['VisitedWebPageContent'] = d.page_content
                docsDict[d.metadata['BrowsingSessionId']] = newVal
            else:
                docsDict[d.metadata['BrowsingSessionId']]['VisitedWebPageContent'] += d.page_content
                
        docstoreturn = []
        
        for x in docsDict.values():
            docstoreturn.append(DocMeta(
                BrowsingSessionId=x['BrowsingSessionId'],
                VisitedWebPageURL=x['VisitedWebPageURL'],
                VisitedWebPageVisitDurationInMilliseconds=x['VisitedWebPageVisitDurationInMilliseconds'],
                VisitedWebPageTitle=x['VisitedWebPageTitle'],
                VisitedWebPageReffererURL=x['VisitedWebPageReffererURL'],
                VisitedWebPageDateWithTimeInISOString=x['VisitedWebPageDateWithTimeInISOString'],
                VisitedWebPageContent=x['VisitedWebPageContent']
            ))
        
        return UserQueryResponse(relateddocs=docstoreturn,response=responsegrp["result"])
    except:
        # Fallback to Similarity Search RAG
        searchchain = SIMILARITY_SEARCH_PROMPT | llm
        
        response = searchchain.invoke({"question": data.query, "context": docstoreturn})
        
        return UserQueryResponse(relateddocs=docstoreturn,response=response.content)
 

# Precision Search
@app.post("/precision")
def get_precision_search_response(data: PrecisionQuery, response_model=PrecisionResponse):
    if(data.apisecretkey != API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    graph = Neo4jGraph(url=data.neourl, username=data.neouser, password=data.neopass)
    
    GRAPH_QUERY = "MATCH (d:Document) WHERE d.VisitedWebPageDateWithTimeInISOString >= " + "'" + data.daterange[0] + "'" + " AND d.VisitedWebPageDateWithTimeInISOString <= "  + "'" + data.daterange[1] + "'"
    
    if(data.timerange[0] >= data.timerange[1]):
        GRAPH_QUERY += " AND d.VisitedWebPageVisitDurationInMilliseconds >= 0"
    else:
        GRAPH_QUERY += " AND d.VisitedWebPageVisitDurationInMilliseconds >= "+ str(data.timerange[0]) + " AND d.VisitedWebPageVisitDurationInMilliseconds <= " + str(data.timerange[1])
    
    if(data.webpageurl):
            GRAPH_QUERY += " AND d.VisitedWebPageURL CONTAINS " + "'" + data.webpageurl.lower() + "'"
            
    if(data.sessionid):
        GRAPH_QUERY += " AND d.BrowsingSessionId = " + "'" + data.sessionid + "'"
        
    GRAPH_QUERY += " RETURN d;"
    
    graphdocs = graph.query(GRAPH_QUERY)
    
    docsDict = {}
    
    for d in graphdocs:
        if d['d']['VisitedWebPageVisitDurationInMilliseconds'] not in docsDict:
            docsDict[d['d']['VisitedWebPageVisitDurationInMilliseconds']] = d['d']
        else:
            docsDict[d['d']['VisitedWebPageVisitDurationInMilliseconds']]['text'] += d['d']['text']
            
    docs = []
    
    for x in docsDict.values():
        docs.append(DocMeta(
            BrowsingSessionId=x['BrowsingSessionId'],
            VisitedWebPageURL=x['VisitedWebPageURL'],
            VisitedWebPageVisitDurationInMilliseconds=x['VisitedWebPageVisitDurationInMilliseconds'],
            VisitedWebPageTitle=x['VisitedWebPageTitle'],
            VisitedWebPageReffererURL=x['VisitedWebPageReffererURL'],
            VisitedWebPageDateWithTimeInISOString=x['VisitedWebPageDateWithTimeInISOString'],
            VisitedWebPageContent=x['text']
        ))
    
    return PrecisionResponse(documents=docs)


# Multi DOC Chat
@app.post("/chat/docs")
def doc_chat_with_history(data: UserQueryWithChatHistory, response_model=DescriptionResponse):
    if(data.apisecretkey != API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=None,
        timeout=None,
        api_key=data.openaikey
    )
    
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
    
    return DescriptionResponse(response=response.content)

      
# DOC DESCRIPTION
@app.post("/kb/doc")
def get_doc_description(data: UserQuery, response_model=DescriptionResponse):
    if(data.apisecretkey != API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    document = data.query
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=None,
        timeout=None,
        api_key=data.openaikey
    )
        
    descriptionchain = DOC_DESCRIPTION_PROMPT | llm
        
    response = descriptionchain.invoke({"document": document})
    
    return DescriptionResponse(response=response.content)
    

# SAVE DOCS TO GRAPH DB
@app.post("/kb/")
def populate_graph(apires: RetrivedDocList, db: Session = Depends(get_db)):
    
    try:
        payload = jwt.decode(apires.token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
            
        print("STARTED")
        # print(apires)
        graph = Neo4jGraph(url=apires.neourl, username=apires.neouser, password=apires.neopass)
        
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=None,
            timeout=None,
            api_key=apires.openaikey
        )
        
        embeddings = OpenAIEmbeddings(
            model="text-embedding-ada-002",
            api_key=apires.openaikey,
        )
        
        llm_transformer = LLMGraphTransformer(llm=llm)

        raw_documents = []

        for doc in apires.documents:
            raw_documents.append(Document(page_content=doc.pageContent, metadata=doc.metadata))

        text_splitter = SemanticChunker(embeddings=embeddings)

        documents = text_splitter.split_documents(raw_documents)   
        graph_documents = llm_transformer.convert_to_graph_documents(documents)


        graph.add_graph_documents(
            graph_documents, 
            baseEntityLabel=True,
            include_source=True
        )
        
                
        structured_llm = llm.with_structured_output(Notifications)
        notifs_extraction_chain = NOTIFICATION_GENERATION_PROMT | structured_llm
        
        notifications = notifs_extraction_chain.invoke({"documents": raw_documents})
        
        notifsdb = []
        
        for text in notifications.notifications:
            notifsdb.append(Notification(text=text))
            
        user = db.query(User).filter(User.username == username).first()
        user.notifications.extend(notifsdb)
        
        db.commit()
        
        print("FINISHED")
        
        return {
            "success": "Graph Will be populated Shortly"
        }
        
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")
    

#Fuction to populate db ( Comment out when running on server )
@app.post("/add/")
def add_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(username=user.username, hashed_password=user.password, graph_config="", llm_config="")
    db.add(db_user)
    db.commit()
    return "Success"
    

#AUTH CODE
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Recommended for Local Setups
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
    db_user = User(username=user.username, hashed_password=hashed_password, graph_config="", llm_config="")
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
            "notifications": user.notifications
        }
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")


@app.get("/user/notification/delete/{token}/{notificationid}")
async def delete_chat_of_user(token: str, notificationid: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=403, detail="Token is invalid or expired")
        
        notificationindb = db.query(Notification).filter(Notification.id == notificationid).first()
        db.delete(notificationindb)
        db.commit()
        return {
            "message": "Notification Deleted"
        }
    except JWTError:
        raise HTTPException(status_code=403, detail="Token is invalid or expired")



    

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)