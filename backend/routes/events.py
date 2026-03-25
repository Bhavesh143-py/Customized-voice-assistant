"""
Events REST API routes.
Public GET endpoints + Protected POST/PUT/DELETE (admin only).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.jwt_auth import get_current_admin
from models.database import AdminUser, get_db
from schemas.schemas import EventCreate, EventResponse, EventUpdate
from services import events_service

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=List[EventResponse], summary="List all active events")
def list_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Public endpoint — returns all active events sorted by date descending.
    Used by the frontend and voice assistant.
    """
    return events_service.get_all_events(db, skip=skip, limit=limit)


@router.get("/upcoming", response_model=List[EventResponse], summary="List upcoming events")
def list_upcoming_events(limit: int = 10, db: Session = Depends(get_db)):
    """
    Public endpoint — returns upcoming events (today and beyond).
    Optimised for the voice assistant to fetch relevant events.
    """
    return events_service.get_upcoming_events(db, limit=limit)


@router.get("/{event_id}", response_model=EventResponse, summary="Get event by ID")
def get_event(event_id: int, db: Session = Depends(get_db)):
    """Public endpoint — get a single event by its ID."""
    event = events_service.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event (admin only)",
)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """Admin-only: create a new college event."""
    return events_service.create_event(db, event_in)


@router.put(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update an event (admin only)",
)
def update_event(
    event_id: int,
    event_in: EventUpdate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """Admin-only: partially update an existing event."""
    event = events_service.update_event(db, event_id, event_in)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event (admin only)",
)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """Admin-only: soft-delete an event."""
    deleted = events_service.delete_event(db, event_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
