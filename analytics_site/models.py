from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)
    url = Column(String)
    referrer = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # User Identification
    session_id = Column(String, index=True)
    visitor_id = Column(String, index=True)
    user_id = Column(String, nullable=True, index=True)
    
    # Device/Browser Info
    screen_width = Column(Integer, nullable=True)
    screen_height = Column(Integer, nullable=True)
    language = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    
    # Custom Data (stored as JSON)
    data = Column(JSON, default=dict)
