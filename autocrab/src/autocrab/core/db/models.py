import uuid
import time
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from autocrab.core.db.database import Base

def generate_uuid():
    return uuid.uuid4().hex

class User(Base):
    """
    Represents an AutoCrab User.
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=True)
    username = Column(String, index=True, nullable=False, default="default_user")
    created_at = Column(Integer, default=lambda: int(time.time()))
    
    sessions = relationship("AgentSession", back_populates="user")

class Channel(Base):
    """
    Represents a communication channel (Slack, Discord, Web UI, Native App).
    """
    __tablename__ = "channels"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    name = Column(String, nullable=False)
    platform = Column(String, nullable=False) # e.g., "slack", "discord", "web", "ios"
    config = Column(JSON, nullable=True) # Channel-specific settings
    is_active = Column(Boolean, default=True)

    sessions = relationship("AgentSession", back_populates="channel")

class AgentSession(Base):
    """
    Represents an active thread of conversation/execution for the Agent.
    """
    __tablename__ = "agent_sessions"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    channel_id = Column(String, ForeignKey("channels.id"), nullable=True)
    
    agent_name = Column(String, nullable=False, default="default_agent")
    status = Column(String, default="active") # active, paused, closed
    created_at = Column(Integer, default=lambda: int(time.time()))
    updated_at = Column(Integer, default=lambda: int(time.time()), onupdate=lambda: int(time.time()))
    
    # Store minimal state here if needed, but primary transcript stays on FS / RAG
    metadata_blob = Column(JSON, nullable=True)

    user = relationship("User", back_populates="sessions")
    channel = relationship("Channel", back_populates="sessions")
