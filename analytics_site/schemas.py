from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class EventPayload(BaseModel):
    """
    Data model for the analytics event upload request.
    This defines the structure of the JSON body sent to /api/track
    """
    event_type: str = Field(..., description="Type of event: 'pageview', 'click', 'custom', etc.")
    url: str = Field(..., description="The full URL where the event occurred")
    referrer: Optional[str] = Field(None, description="The referrer URL")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Client-side timestamp")
    
    # User Identification
    session_id: str = Field(..., description="Ephemeral session ID")
    visitor_id: Optional[str] = Field(None, description="Long-term visitor ID")
    user_id: Optional[str] = Field(None, description="Authenticated User ID (hashed/anonymized if possible)")
    
    # Device/Browser Info (Client can send these, or server can parse User-Agent)
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    language: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Custom Data
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary event data (e.g., course_id)")

class EventResponse(BaseModel):
    status: str = "ok"
    received_at: datetime
