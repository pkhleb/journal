from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
        email: EmailStr
        username: str
        password: str

class UserOut(BaseModel):
        id: int
        email: str
        created_at: datetime
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


