from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator
from app.timeutil import is_valid_timezone
from typing import Optional
from datetime import date, datetime

class UserCreate(BaseModel):
        email: EmailStr
        username: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9]+$")
        password: str
        timezone: Optional[str] = None

        @field_validator("timezone")
        @classmethod
        def _check_timezone(cls, v):
                if v is not None and not is_valid_timezone(v):
                        raise ValueError("unknown IANA timezone")
                return v

class UserUpdate(BaseModel):
        timezone: str

        @field_validator("timezone")
        @classmethod
        def _check_timezone(cls, v):
                if not is_valid_timezone(v):
                        raise ValueError("unknown IANA timezone")
                return v

class UserOut(BaseModel):
        id: int
        email: str
        created_at: datetime
        is_admin: bool
        timezone: str
        class Config:
                from_attributes = True

class Token(BaseModel):
        access_token: str
        token_type: str

class EntryCreate(BaseModel):
        prose: Optional[str] = None
        metric_type: Optional[str] = None
        metric_data: Optional[dict] = None

        @model_validator(mode="after")
        def _check_metric(self):
                if self.metric_type is not None and not self.metric_type.strip():
                        raise ValueError("metric_type must not be empty")
                if self.metric_type is not None and self.metric_data is None:
                        raise ValueError("metric_data is required when metric_type is set")
                if self.metric_type is None and self.metric_data is not None:
                        raise ValueError("metric_type is required when metric_data is set")
                if self.metric_type == "exercise":
                        name = self.metric_data.get("name")
                        if not isinstance(name, str) or not name.strip():
                                raise ValueError("exercise metric_data requires a non-empty name")
                return self

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
