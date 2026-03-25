"""
Events service layer — CRUD operations with clean separation from routes.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from models.database import Event
from schemas.schemas import EventCreate, EventUpdate


def get_all_events(db: Session, skip: int = 0, limit: int = 100) -> List[Event]:
    """Return all active events, newest first."""
    return (
        db.query(Event)
        .filter(Event.is_active == True)
        .order_by(Event.date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_event_by_id(db: Session, event_id: int) -> Optional[Event]:
    """Return a single event by ID (or None if not found/inactive)."""
    return db.query(Event).filter(Event.id == event_id, Event.is_active == True).first()


def get_upcoming_events(db: Session, limit: int = 10) -> List[Event]:
    """Return upcoming events (date >= today), sorted ascending."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return (
        db.query(Event)
        .filter(Event.is_active == True, Event.date >= today)
        .order_by(Event.date.asc())
        .limit(limit)
        .all()
    )


def create_event(db: Session, event_in: EventCreate) -> Event:
    """Create and persist a new event."""
    now = datetime.utcnow()
    db_event = Event(
        title=event_in.title,
        description=event_in.description,
        date=event_in.date,
        time=event_in.time,
        location=event_in.location,
        created_at=now,
        updated_at=now,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def update_event(db: Session, event_id: int, event_in: EventUpdate) -> Optional[Event]:
    """
    Partially update an event (only provided fields change).

    Returns:
        Updated Event or None if not found
    """
    db_event = get_event_by_id(db, event_id)
    if not db_event:
        return None

    update_data = event_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_event, field, value)
    db_event.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_event)
    return db_event


def delete_event(db: Session, event_id: int) -> bool:
    """
    Soft-delete an event (sets is_active=False).

    Returns:
        True if deleted, False if not found
    """
    db_event = get_event_by_id(db, event_id)
    if not db_event:
        return False

    db_event.is_active = False
    db_event.updated_at = datetime.utcnow()
    db.commit()
    return True


def format_events_for_voice(events: List[Event]) -> str:
    """
    Format events list as natural-language text for the voice assistant RAG context.

    Returns:
        Formatted string ready to inject into LLM context
    """
    if not events:
        return "No upcoming events are currently scheduled."

    lines = ["Upcoming college events:"]
    for evt in events:
        parts = [f"- {evt.title} on {evt.date}"]
        if evt.time:
            parts[0] += f" at {evt.time}"
        if evt.location:
            parts[0] += f" at {evt.location}"
        if evt.description:
            parts.append(f"  Details: {evt.description}")
        lines.extend(parts)

    return "\n".join(lines)
