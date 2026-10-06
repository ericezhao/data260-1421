import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import SessionToken

SESSION_TTL_MINUTES = 30


def create_session(db: Session, user_id: int) -> SessionToken:
    now = datetime.now(timezone.utc)
    db.query(SessionToken).filter(SessionToken.expires_at < now).delete()
    token = secrets.token_hex(32)
    expires = now + timedelta(minutes=SESSION_TTL_MINUTES)
    row = SessionToken(id=token, user_id=user_id, expires_at=expires)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, token: str) -> SessionToken | None:
    row = db.query(SessionToken).filter(SessionToken.id == token).first()
    if not row:
        return None
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        return None
    return row


def delete_session(db: Session, token: str) -> bool:
    row = db.query(SessionToken).filter(SessionToken.id == token).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
