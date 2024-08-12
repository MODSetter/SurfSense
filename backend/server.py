from __future__ import annotations

from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from envs import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, API_SECRET_KEY, SECRET_KEY
from prompts import CYPHER_QA_PROMPT, DOC_DESCRIPTION_PROMPT, SIMILARITY_SEARCH_PROMPT , CYPHER_GENERATION_PROMPT, DOCUMENT_METADATA_EXTRACTION_PROMT
from pydmodels import DescriptionResponse, UserQuery, DocMeta, RetrivedDocList, UserQueryResponse
from langchain_experimental.text_splitter import SemanticChunker

#Our Imps
from LLMGraphTransformer import LLMGraphTransformer
from langchain_openai import ChatOpenAI

# Auth Libs
from fastapi import FastAPI, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from models import User
from database import SessionLocal, engine
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()



  
  
@app.post("/")
def get_user_query_response(data: UserQuery, response_model=UserQueryResponse):
    
    if(data.apisecretkey != API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    
    query = data.query
    
    graph = Neo4jGraph(url=data.neourl, username=data.neouser, password=data.neopass)
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=None,
        timeout=None,
        api_key=data.openaikey
    )
    
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
    
    docs = vector_index.similarity_search(query,k=5)
    
    docstoreturn = []
    
    for doc in docs:
        docstoreturn.append(
            DocMeta(
                BrowsingSessionId=doc.metadata["BrowsingSessionId"] if "BrowsingSessionId" in doc.metadata.keys() else "NOT AVAILABLE",
                VisitedWebPageURL=doc.metadata["VisitedWebPageURL"] if "VisitedWebPageURL" in doc.metadata.keys()else "NOT AVAILABLE",
                VisitedWebPageTitle=doc.metadata["VisitedWebPageTitle"] if "VisitedWebPageTitle" in doc.metadata.keys() else "NOT AVAILABLE",
                VisitedWebPageDateWithTimeInISOString= doc.metadata["VisitedWebPageDateWithTimeInISOString"] if "VisitedWebPageDateWithTimeInISOString" in doc.metadata.keys() else "NOT AVAILABLE",
                VisitedWebPageReffererURL= doc.metadata["VisitedWebPageReffererURL"] if "VisitedWebPageReffererURL" in doc.metadata.keys() else "NOT AVAILABLE",
                VisitedWebPageVisitDurationInMilliseconds= doc.metadata["VisitedWebPageVisitDurationInMilliseconds"] if "VisitedWebPageVisitDurationInMilliseconds" in doc.metadata.keys() else None,
                VisitedWebPageContent= doc.page_content if doc.page_content else "NOT AVAILABLE"
            )
        )
                
    docstoreturn = [i for n, i in enumerate(docstoreturn) if i not in docstoreturn[n + 1:]]


    try:
        response = chain.invoke({"query": query})
        if "don't know" in response["result"]:
            raise Exception("No response from graph")
        
        structured_llm = llm.with_structured_output(RetrivedDocList)
        doc_extract_chain = DOCUMENT_METADATA_EXTRACTION_PROMT | structured_llm
        
        query = doc_extract_chain.invoke(response["intermediate_steps"][1]["context"])
        
        docs = vector_index.similarity_search(query.searchquery,k=5)
    
        docstoreturn = []
        
        for doc in docs:
            docstoreturn.append(
                DocMeta(
                    BrowsingSessionId=doc.metadata["BrowsingSessionId"] if "BrowsingSessionId" in doc.metadata.keys() else "NOT AVAILABLE",
                    VisitedWebPageURL=doc.metadata["VisitedWebPageURL"] if "VisitedWebPageURL" in doc.metadata.keys()else "NOT AVAILABLE",
                    VisitedWebPageTitle=doc.metadata["VisitedWebPageTitle"] if "VisitedWebPageTitle" in doc.metadata.keys() else "NOT AVAILABLE",
                    VisitedWebPageDateWithTimeInISOString= doc.metadata["VisitedWebPageDateWithTimeInISOString"] if "VisitedWebPageDateWithTimeInISOString" in doc.metadata.keys() else "NOT AVAILABLE",
                    VisitedWebPageReffererURL= doc.metadata["VisitedWebPageReffererURL"] if "VisitedWebPageReffererURL" in doc.metadata.keys() else "NOT AVAILABLE",
                    VisitedWebPageVisitDurationInMilliseconds= doc.metadata["VisitedWebPageVisitDurationInMilliseconds"] if "VisitedWebPageVisitDurationInMilliseconds" in doc.metadata.keys() else None,
                    VisitedWebPageContent= doc.page_content if doc.page_content else "NOT AVAILABLE"
                )
            )
                    
        docstoreturn = [i for n, i in enumerate(docstoreturn) if i not in docstoreturn[n + 1:]]
        
        return UserQueryResponse(relateddocs=docstoreturn,response=response["result"])
    except:
        # Fallback to Similarity Search RAG
        searchchain = SIMILARITY_SEARCH_PROMPT | llm
        
        response = searchchain.invoke({"question": query, "context": docs})
        
        return UserQueryResponse(relateddocs=docstoreturn,response=response.content)
    
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
def populate_graph(apires: RetrivedDocList):
    if(apires.apisecretkey != API_SECRET_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
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
    
    print("FINISHED")
    
    return {
        "success": "Graph Will be populated Shortly"
    }
    



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

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserCreate(BaseModel):
    username: str
    password: str
    apisecretkey: str

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)