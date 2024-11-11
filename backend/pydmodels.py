# This have many unused shit will clean in future
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


class CreatePodcast(BaseModel):
    token: str
    search_space_id: int
    title: str
    wordcount: int
    podcast_content: str


class CreateStorageSpace(BaseModel):
    name: str
    description: str
    token : str


class Reference(BaseModel):
    id: str = Field(..., description="reference no")
    title: str = Field(..., description="reference title.")
    source: str = Field(..., description="reference Source or URL. Prefer URL only include file names if no URL available.")


class AIAnswer(BaseModel):
    answer: str = Field(..., description="The provided answer, excluding references, but including in-text citation numbers such as [1], [2], (1), (2), etc.")
    references: List[Reference] = Field(..., description="References")


class DocWithContent(BaseModel):
    DocMetadata: Optional[str] = Field(default=None, description="Document Metadata")
    Content: Optional[str] = Field(default=None, description="Document Page Content")
      
class DocumentsToDelete(BaseModel):
    ids_to_delete: List[str]
    token: str   
    
class UserQuery(BaseModel):
    query: str
    search_space: str
    token: str
    
class MainUserQuery(BaseModel):
    query: str
    search_space: str
    token: str
    
class ChatHistory(BaseModel):
    type: str
    content: str | List[DocMeta] | List[str]
    
class UserQueryWithChatHistory(BaseModel):
    chat: List[ChatHistory]
    query: str
    token: str
    
class DescriptionResponse(BaseModel):
    response: str

class RetrivedDocListItem(BaseModel):
    metadata: DocMeta
    pageContent: str

class RetrivedDocList(BaseModel):
    documents: List[RetrivedDocListItem]
    search_space_id: int
    token: str
    
class UserQueryResponse(BaseModel):
    response: str
    relateddocs: List[DocWithContent]
    
class NewUserQueryResponse(BaseModel):
    response: str
    sources: List[Reference]
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