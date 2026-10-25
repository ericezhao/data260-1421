from database import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class Owner(Base):
    __tablename__ = "owners"
    __table_args__ = (UniqueConstraint("email", name="uq_owners_email"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    inspections = relationship("Inspection", back_populates="owner")


class Inspection(Base):
    __tablename__ = "inspections"
    __table_args__ = (UniqueConstraint("inspection_code", name="uq_inspections_code"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    restaurant_name = Column(String(255), nullable=False)
    cuisine = Column(String(255), nullable=False, index=True)
    inspection_code = Column(String(20), nullable=False)
    score = Column(Integer, nullable=False, default=100, server_default="100")
    # RESTRICT: an owner who still has inspections cannot be deleted
    owner_id = Column(
        Integer,
        ForeignKey("owners.id", ondelete="RESTRICT", name="fk_inspections_owner"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("Owner", back_populates="inspections")
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
    # JWT login uses username + role (reader | writer | moderator)
    username = Column(String(80), nullable=True, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="reader", server_default="reader")


class SessionToken(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
