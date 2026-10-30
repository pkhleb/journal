from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import date, datetime

class UserCreate(BaseModel):
        email: EmailStr
        username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9]+$")
        password: str

class UserOut(BaseModel):
        id: int
        email: str
        created_at: datetime
        is_admin: bool
        class Config:
                from_attributes = True

class Token(BaseModel):
        access_token: str
        token_type: str

class EntryCreate(BaseModel):
        prose: Optional[str] = None
        metric_type: Optional[str] = None
        metric_data: Optional[dict] = None

class EntryOut(BaseModel):
        id: int
        prose: Optional[str]
        metric_type: Optional[str]
        metric_data: Optional[dict]
        created_at: datetime
        class Config:
                from_attributes = True

class InventoryItemCreate(BaseModel):
        name: str
        items: list[dict]

class InventoryItemOut(BaseModel):
        id: int
        name: str
        items: list[dict]
        created_at: datetime
        class Config:
                from_attributes: True

class PredictionEventOut(BaseModel):
        id: int
        user_id: int
        created_at: datetime
        resolved: bool
        resolved_at: Optional[datetime]
        data: dict
        latency_ms: Optional[float]

        class Config:
                from_attributes = True

class ActivityBucket(BaseModel):
        period_start: date
        posts: int
        users: int
