from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from app.database import Base

class User(Base):
        __tablename__ = "users"

        id              = Column(Integer, primary_key=True, index=True)
        email           = Column(String, unique=True, index=True, nullable=False)
        username        = Column(String, unique=True, index=True, nullable=False)
        hashed_password = Column(String, nullable=False)
        created_at      = Column(DateTime(timezone=True), server_default=func.now())
        entries         = relationship("Entry", back_populates="user")
        inventory       = relationship("InventoryItem", back_populates="user")
        failed_login_attempts = Column(Integer, default=0)
        locked_until          = Column(DateTime(timezone=True), nullable=True)

class Entry(Base):
        __tablename__ = "entries"
        
        id              = Column(Integer, primary_key=True, index=True)
        user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
        prose           = Column(Text, nullable=True)
        metric_type     = Column(String, nullable=True)
        metric_data     = Column(JSONB, nullable=True)
        created_at      = Column(DateTime(timezone=True), server_default=func.now())
        user            = relationship("User", back_populates="entries")

class InventoryItem(Base):
        __tablename__ = "inventory"

        id              = Column(Integer, primary_key=True, index=True)
        user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
        name            = Column(String, nullable=False)
        items           = Column(JSONB, nullable=False)
        created_at      = Column(DateTime(timezone=True), server_default=func.now())
        user            = relationship("User", back_populates="inventory")
