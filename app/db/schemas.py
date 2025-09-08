from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class EventBase(BaseModel):
    title: str = Field(..., example="Team Meeting")
    description: Optional[str] = Field(None, example="Discuss updates")
    start_time: datetime = Field(..., example="2025-09-04T15:15:00")
    end_time: Optional[datetime] = Field(None, example="2025-09-04T16:15:00")

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class Event(EventBase):
    id: int
    google_event_id: Optional[str] = None

    class Config:
        orm_mode = True
