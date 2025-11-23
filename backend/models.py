from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Issue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "open"
    classification: Optional[str] = None

    messages: List["Message"] = Relationship(back_populates="issue")

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slack_ts: str = Field(index=True, unique=True)
    channel_id: str
    user_id: str
    text: str
    timestamp: datetime
    classification: str 
    confidence: float
    is_relevant: bool
    embedding: Optional[str] = None 
    
    issue_id: Optional[int] = Field(default=None, foreign_key="issue.id")
    issue: Optional[Issue] = Relationship(back_populates="messages")
