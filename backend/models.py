from typing import List
from database import Base, engine
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import relationship

class BaseModel(Base):
    __abstract__ = True
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)


class Notification(BaseModel):
    __tablename__ = "notifications"

    text = Column(String)
    user_id = Column(ForeignKey('users.id'))
    user = relationship('User')


class Chat(BaseModel):
    __tablename__ = "chats"

    type = Column(String)
    title = Column(String)
    chats_list = Column(String)
    user_id = Column(ForeignKey('users.id'))
    user = relationship('User')
    
class User(BaseModel):
    __tablename__ = "users"

    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    graph_config = Column(String)
    llm_config = Column(String)
    chats = relationship(Chat)
    notifications = relationship(Notification)

# Create the database tables if they don't exist
User.metadata.create_all(bind=engine)
