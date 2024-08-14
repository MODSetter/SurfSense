from pydantic import BaseModel, Field
from typing import List, Optional

class UserQuery(BaseModel):
    query: str
    neourl: str
    neouser: str
    neopass: str
    openaikey: str
    apisecretkey: str
    
class DescriptionResponse(BaseModel):
    response: str

    
class DocMeta(BaseModel):
    BrowsingSessionId: Optional[str] = Field(default=None, description="BrowsingSessionId of Document")
    VisitedWebPageURL: Optional[str] = Field(default=None, description="VisitedWebPageURL of Document")
    VisitedWebPageTitle: Optional[str] = Field(default=None, description="VisitedWebPageTitle of Document")
    VisitedWebPageDateWithTimeInISOString: Optional[str] = Field(default=None, description="VisitedWebPageDateWithTimeInISOString of Document")
    VisitedWebPageReffererURL: Optional[str] = Field(default=None, description="VisitedWebPageReffererURL of Document")
    VisitedWebPageVisitDurationInMilliseconds: Optional[int] = Field(default=None, description="VisitedWebPageVisitDurationInMilliseconds of Document"),
    VisitedWebPageContent: Optional[str] = Field(default=None, description="Visited WebPage Content in markdown of Document")
    
class RetrivedDocListItem(BaseModel):
    metadata: DocMeta
    pageContent: str

class RetrivedDocList(BaseModel):
    documents: List[RetrivedDocListItem]
    neourl: str
    neouser: str
    neopass: str
    openaikey: str
    apisecretkey: str
    
    
class UserQueryResponse(BaseModel):
    response: str
    relateddocs: List[DocMeta]
    

class VectorSearchQuery(BaseModel):
    searchquery: str
    