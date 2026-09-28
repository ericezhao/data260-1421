from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    restaurant_name = Column(String(255), nullable=False)
    cuisine = Column(String(255), nullable=False)

    # passive_deletes: let MySQL's ON DELETE CASCADE remove violations when an inspection is deleted
    violations = relationship("Violation", passive_deletes=True)


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    inspection_id = Column(
        Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    description = Column(String(255), nullable=False)
    severity = Column(String(20), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)


class SessionToken(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
