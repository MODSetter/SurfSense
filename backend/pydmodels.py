from pydantic import BaseModel, Field
from typing import List, Optional

class UserCreate(BaseModel):
    username: str
    password: str
    apisecretkey: str

class DocMeta(BaseModel):
    BrowsingSessionId: Optional[str] = Field(default=None, description="BrowsingSessionId of Document")
    VisitedWebPageURL: Optional[str] = Field(default=None, description="VisitedWebPageURL of Document")
    VisitedWebPageTitle: Optional[str] = Field(default=None, description="VisitedWebPageTitle of Document")
    VisitedWebPageDateWithTimeInISOString: Optional[str] = Field(default=None, description="VisitedWebPageDateWithTimeInISOString of Document")
    VisitedWebPageReffererURL: Optional[str] = Field(default=None, description="VisitedWebPageReffererURL of Document")
    VisitedWebPageVisitDurationInMilliseconds: Optional[int] = Field(default=None, description="VisitedWebPageVisitDurationInMilliseconds of Document"),
    
# class DocWithContent(BaseModel):
#     BrowsingSessionId: Optional[str] = Field(default=None, description="BrowsingSessionId of Document")
#     VisitedWebPageURL: Optional[str] = Field(default=None, description="VisitedWebPageURL of Document")
#     VisitedWebPageTitle: Optional[str] = Field(default=None, description="VisitedWebPageTitle of Document")
#     VisitedWebPageDateWithTimeInISOString: Optional[str] = Field(default=None, description="VisitedWebPageDateWithTimeInISOString of Document")
#     VisitedWebPageReffererURL: Optional[str] = Field(default=None, description="VisitedWebPageReffererURL of Document")
#     VisitedWebPageVisitDurationInMilliseconds: Optional[int] = Field(default=None, description="VisitedWebPageVisitDurationInMilliseconds of Document"),
#     VisitedWebPageContent: Optional[str] = Field(default=None, description="Visited WebPage Content in markdown of Document")



class Reference(BaseModel):
    id: str = Field(..., description="reference no")
    title: str = Field(..., description="reference title")
    url: str = Field(..., description="reference url")


class AIAnswer(BaseModel):
    answer: str = Field(..., description="Given Answer including its intext citation no's like [1], [2] etc.")
    references: List[Reference] = Field(..., description="References")


class DocWithContent(BaseModel):
    DocMetadata: Optional[str] = Field(default=None, description="Document Metadata")
    Content: Optional[str] = Field(default=None, description="Document Page Content")
      
class DocumentsToDelete(BaseModel):
    ids_to_delete: List[str]
    openaikey: str
    token: str   
    
class UserQuery(BaseModel):
    query: str
    search_space: str
    openaikey: str
    token: str
    
class ChatHistory(BaseModel):
    type: str
    content: str | List[DocMeta] | List[str]
    
class UserQueryWithChatHistory(BaseModel):
    chat: List[ChatHistory]
    query: str
    openaikey: str
    token: str
    
class DescriptionResponse(BaseModel):
    response: str

class RetrivedDocListItem(BaseModel):
    metadata: DocMeta
    pageContent: str

class RetrivedDocList(BaseModel):
    documents: List[RetrivedDocListItem]
    search_space: str | None
    openaikey: str
    token: str
    
class UserQueryResponse(BaseModel):
    response: str
    relateddocs: List[DocWithContent]
    
class NewUserChat(BaseModel):
    token: str
    type: str
    title: str
    chats_list: str
    
class ChatToUpdate(BaseModel):
    chatid: str
    token: str
    chats_list: str