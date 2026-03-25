"""
Notifications service layer — CRUD operations for college announcements.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from models.database import Notification
from schemas.schemas import NotificationCreate, NotificationUpdate


def get_all_notifications(db: Session, skip: int = 0, limit: int = 100) -> List[Notification]:
    """Return all active notifications, newest first."""
    return (
        db.query(Notification)
        .filter(Notification.is_active == True)
        .order_by(Notification.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_notification_by_id(db: Session, notif_id: int) -> Optional[Notification]:
    """Return a single notification by ID."""
    return db.query(Notification).filter(
        Notification.id == notif_id, Notification.is_active == True
    ).first()


def get_recent_notifications(db: Session, limit: int = 5) -> List[Notification]:
    """Return the N most recent active notifications."""
    return (
        db.query(Notification)
        .filter(Notification.is_active == True)
        .order_by(Notification.timestamp.desc())
        .limit(limit)
        .all()
    )


def create_notification(db: Session, notif_in: NotificationCreate) -> Notification:
    """Create and persist a new notification."""
    now = datetime.utcnow()
    db_notif = Notification(
        title=notif_in.title,
        message=notif_in.message,
        timestamp=now,
        created_at=now,
        updated_at=now,
    )
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)
    return db_notif


def update_notification(
    db: Session, notif_id: int, notif_in: NotificationUpdate
) -> Optional[Notification]:
    """
    Partially update a notification.

    Returns:
        Updated Notification or None if not found
    """
    db_notif = get_notification_by_id(db, notif_id)
    if not db_notif:
        return None

    update_data = notif_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_notif, field, value)
    db_notif.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_notif)
    return db_notif


def delete_notification(db: Session, notif_id: int) -> bool:
    """
    Soft-delete a notification.

    Returns:
        True if deleted, False if not found
    """
    db_notif = get_notification_by_id(db, notif_id)
    if not db_notif:
        return False

    db_notif.is_active = False
    db_notif.updated_at = datetime.utcnow()
    db.commit()
    return True


def format_notifications_for_voice(notifications: List[Notification]) -> str:
    """
    Format notifications as natural-language text for the voice assistant.

    Returns:
        Formatted string for LLM context injection
    """
    if not notifications:
        return "There are no recent announcements."

    lines = ["Recent college announcements:"]
    for n in notifications:
        date_str = n.timestamp.strftime("%B %d, %Y") if n.timestamp else ""
        lines.append(f"- {n.title}: {n.message}" + (f" (Posted: {date_str})" if date_str else ""))

    return "\n".join(lines)
