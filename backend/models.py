from datetime import datetime
from typing import List
from database import Base, engine
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine
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
    
    user_id = Column(ForeignKey('users.id'))
    user = relationship('User')

    
class Documents(BaseModel):
    __tablename__ = "documents"
    
    title = Column(String)
    
    created_at = Column(DateTime, default=datetime.now)
    file_type = Column(String)
    document_metadata = Column(String)
    page_content = Column(String)
    desc_vector_start = Column(Integer, default=0)
    desc_vector_end = Column(Integer, default=0)
    
    search_space_id = Column(ForeignKey('searchspaces.id'))
    search_space = relationship('SearchSpace')
    
    user_id = Column(ForeignKey('users.id'))
    user = relationship('User')
    
class SearchSpace(BaseModel):
    __tablename__ = "searchspaces"
    
    search_space = Column(String, unique=True)
    
    documents = relationship(Documents)
    
class User(BaseModel):
    __tablename__ = "users"

    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    chats = relationship(Chat, order_by="Chat.id")
    documents = relationship(Documents, order_by="Documents.id")
    

# Create the database tables if they don't exist
User.metadata.create_all(bind=engine)
