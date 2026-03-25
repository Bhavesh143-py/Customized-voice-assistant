"""
Notifications REST API routes.
Public GET + Protected POST/PUT/DELETE (admin only).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.jwt_auth import get_current_admin
from models.database import AdminUser, get_db
from schemas.schemas import NotificationCreate, NotificationResponse, NotificationUpdate
from services import notifications_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse], summary="List all notifications")
def list_notifications(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Public: returns all active notifications, newest first."""
    return notifications_service.get_all_notifications(db, skip=skip, limit=limit)


@router.get("/recent", response_model=List[NotificationResponse], summary="Recent notifications")
def recent_notifications(limit: int = 5, db: Session = Depends(get_db)):
    """Public: returns the N most recent notifications. Used by the voice assistant."""
    return notifications_service.get_recent_notifications(db, limit=limit)


@router.get("/{notif_id}", response_model=NotificationResponse, summary="Get notification by ID")
def get_notification(notif_id: int, db: Session = Depends(get_db)):
    """Public: get a single notification."""
    notif = notifications_service.get_notification_by_id(db, notif_id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notif


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create notification (admin only)",
)
def create_notification(
    notif_in: NotificationCreate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """Admin-only: post a new announcement/notification."""
    return notifications_service.create_notification(db, notif_in)


@router.put(
    "/{notif_id}",
    response_model=NotificationResponse,
    summary="Update notification (admin only)",
)
def update_notification(
    notif_id: int,
    notif_in: NotificationUpdate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """Admin-only: update title/message of an existing notification."""
    notif = notifications_service.update_notification(db, notif_id, notif_in)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notif


@router.delete(
    "/{notif_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification (admin only)",
)
def delete_notification(
    notif_id: int,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """Admin-only: soft-delete a notification."""
    deleted = notifications_service.delete_notification(db, notif_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
