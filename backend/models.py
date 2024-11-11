from datetime import datetime
# from typing import List
from database import Base, engine
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, create_engine
from sqlalchemy.orm import relationship

class BaseModel(Base):
    __abstract__ = True
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)


class Chat(BaseModel):
    __tablename__ = "chats"

    type = Column(String)
    title = Column(String)
    chats_list = Column(String)
    
    search_space_id = Column(Integer, ForeignKey('searchspaces.id'))
    search_space = relationship('SearchSpace', back_populates='chats')

    
class Documents(BaseModel):
    __tablename__ = "documents"
    
    title = Column(String)
    
    created_at = Column(DateTime, default=datetime.now)
    file_type = Column(String)
    document_metadata = Column(String)
    page_content = Column(String)
    
    summary_vector_id = Column(String)
    
    search_space_id = Column(Integer, ForeignKey("searchspaces.id"))
    search_space = relationship("SearchSpace", back_populates="documents")
    
    
class Podcast(BaseModel):
    __tablename__ = "podcasts"
    
    title = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    is_generated = Column(Boolean, default=False)
    podcast_content = Column(String, default="")
    file_location = Column(String, default="")
    
    search_space_id = Column(Integer, ForeignKey("searchspaces.id"))
    search_space = relationship("SearchSpace", back_populates="podcasts")
    
    
    
class SearchSpace(BaseModel):
    __tablename__ = "searchspaces"
    
    name = Column(String, index=True)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="search_spaces")
    
    documents = relationship("Documents", back_populates="search_space", order_by="Documents.id")
    podcasts = relationship("Podcast", back_populates="search_space", order_by="Podcast.id")

    chats = relationship('Chat', back_populates='search_space', order_by='Chat.id')
    
class User(BaseModel):
    __tablename__ = "users"

    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    search_spaces = relationship("SearchSpace", back_populates="user")
    

# Create the database tables if they don't exist
User.metadata.create_all(bind=engine)