"""
SQLAlchemy database models for PVG College Voice Assistant.
Supports SQLite (dev) and PostgreSQL (prod) via DATABASE_URL env var.
"""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String, Text, create_engine
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ── Database URL ───────────────────────────────────────────────────────────────
# Default: SQLite for local dev
# Set DATABASE_URL=postgresql://user:pass@host/db for production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pvg_college.db")

# SQLite needs check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Event(Base):
    """College events — seminars, fests, sports, etc."""
    __tablename__ = "events"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    date        = Column(String(20), nullable=False)   # ISO date: YYYY-MM-DD
    time        = Column(String(10), nullable=True)    # HH:MM
    location    = Column(String(255), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active   = Column(Boolean, default=True)


class Notification(Base):
    """Announcements and notices for students/staff."""
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    title      = Column(String(255), nullable=False)
    message    = Column(Text, nullable=False)
    timestamp  = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active  = Column(Boolean, default=True)


class AdminUser(Base):
    """Admin users for the dashboard."""
    __tablename__ = "admin_users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(100), unique=True, nullable=False, index=True)
    email         = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


def get_db():
    """Dependency injection: yield DB session, close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
