from pydantic import BaseModel, Field
from typing import List, Optional

class DocMeta(BaseModel):
    BrowsingSessionId: Optional[str] = Field(default=None, description="BrowsingSessionId of Document")
    VisitedWebPageURL: Optional[str] = Field(default=None, description="VisitedWebPageURL of Document")
    VisitedWebPageTitle: Optional[str] = Field(default=None, description="VisitedWebPageTitle of Document")
    VisitedWebPageDateWithTimeInISOString: Optional[str] = Field(default=None, description="VisitedWebPageDateWithTimeInISOString of Document")
    VisitedWebPageReffererURL: Optional[str] = Field(default=None, description="VisitedWebPageReffererURL of Document")
    VisitedWebPageVisitDurationInMilliseconds: Optional[int] = Field(default=None, description="VisitedWebPageVisitDurationInMilliseconds of Document"),
    VisitedWebPageContent: Optional[str] = Field(default=None, description="Visited WebPage Content in markdown of Document")
    
class PrecisionQuery(BaseModel):
    sessionid: Optional[str] = Field(default=None)
    webpageurl: Optional[str] = Field(default=None)
    daterange: Optional[List[str]]
    timerange: Optional[List[int]]
    neourl: str
    neouser: str
    neopass: str
    openaikey: str
    apisecretkey: str
    
class PrecisionResponse(BaseModel):
    documents: List[DocMeta]
    
    
    
class UserQuery(BaseModel):
    query: str
    neourl: str
    neouser: str
    neopass: str
    openaikey: str
    apisecretkey: str
    
class ChatHistory(BaseModel):
    type: str
    content: str | List[DocMeta]
    
class UserQueryWithChatHistory(BaseModel):
    chat: List[ChatHistory]
    query: str
    neourl: str
    neouser: str
    neopass: str
    openaikey: str
    apisecretkey: str
    
    
class DescriptionResponse(BaseModel):
    response: str

    
class RetrivedDocListItem(BaseModel):
    metadata: DocMeta
    pageContent: str

class RetrivedDocList(BaseModel):
    documents: List[RetrivedDocListItem]
    neourl: str
    neouser: str
    neopass: str
    openaikey: str
    token: str
    
    
class UserQueryResponse(BaseModel):
    response: str
    relateddocs: List[DocMeta]
    

class VectorSearchQuery(BaseModel):
    searchquery: str
    
    
class NewUserData(BaseModel):
    token: str
    userid: str
    chats: str
    notifications: str
    
class NewUserChat(BaseModel):
    token: str
    type: str
    title: str
    chats_list: str
    
    
class ChatToUpdate(BaseModel):
    chatid: str
    token: str
    # type: str
    # title: str
    chats_list: str
    
class GraphDocs(BaseModel):
    documents: List[RetrivedDocListItem]
    token: str
    
    
class Notifications(BaseModel):
    notifications: List[str]
    