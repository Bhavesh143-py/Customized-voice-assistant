"""
Pydantic v2 schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Event Schemas ──────────────────────────────────────────────────────────────

class EventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Event title")
    description: Optional[str] = Field(None, description="Event details")
    date: str = Field(..., description="Event date (YYYY-MM-DD)")
    time: Optional[str] = Field(None, description="Event time (HH:MM)")
    location: Optional[str] = Field(None, max_length=255, description="Venue/location")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("time must be in HH:MM format")
        return v


class EventCreate(EventBase):
    """Schema for creating a new event."""
    pass


class EventUpdate(BaseModel):
    """Schema for partial event updates (all fields optional)."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")
        return v


class EventResponse(EventBase):
    """Schema for event API responses."""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


# ── Notification Schemas ───────────────────────────────────────────────────────

class NotificationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)


class NotificationCreate(NotificationBase):
    """Schema for creating a new notification."""
    pass


class NotificationUpdate(BaseModel):
    """Schema for partial notification updates."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    message: Optional[str] = Field(None, min_length=1)


class NotificationResponse(NotificationBase):
    """Schema for notification API responses."""
    id: int
    timestamp: datetime
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


# ── Auth Schemas ───────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Min 8 characters")


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

    model_config = {"from_attributes": True}
