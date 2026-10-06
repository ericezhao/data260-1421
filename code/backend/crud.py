from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

import models
import schema

OWNER_FIELDS = {"name": "name", "phone": "phone", "email": "email"}
INSPECTION_FIELDS = {
    "restaurantName": "restaurant_name",
    "cuisine": "cuisine",
    "inspectionCode": "inspection_code",
    "score": "score",
    "ownerId": "owner_id",
}


def _commit(db: Session, conflict_detail: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_detail)


# ----- owners -----
def create_owner(db: Session, payload: schema.OwnerCreate):
    record = models.Owner(**payload.model_dump())
    db.add(record)
    _commit(db, f"Owner email {payload.email} already exists")
    db.refresh(record)
    return record


def get_owners(db: Session, skip: int, limit: int):
    return (
        db.query(models.Owner)
        .order_by(models.Owner.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_owner(db: Session, owner_id: int):
    record = db.get(models.Owner, owner_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Owner {owner_id} not found")
    return record


def update_owner(db: Session, owner_id: int, payload: schema.OwnerUpdate):
    record = get_owner(db, owner_id)
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(record, OWNER_FIELDS[key], value)
    _commit(db, f"Owner email {payload.email} already exists")
    db.refresh(record)
    return record


def delete_owner(db: Session, owner_id: int):
    record = get_owner(db, owner_id)
    count = (
        db.query(func.count(models.Inspection.id))
        .filter(models.Inspection.owner_id == owner_id)
        .scalar()
    )
    if count:
        raise HTTPException(
            status_code=409,
            detail=f"Owner {owner_id} still has {count} inspection(s) and cannot be deleted",
        )
    db.delete(record)
    _commit(db, f"Owner {owner_id} still has inspections and cannot be deleted")


def get_inspections_by_owner(db: Session, owner_id: int, skip: int, limit: int):
    get_owner(db, owner_id)
    return (
        db.query(models.Inspection)
        .filter(models.Inspection.owner_id == owner_id)
        .order_by(models.Inspection.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ----- inspections -----
def create_inspection(db: Session, payload: schema.InspectionCreate):
    get_owner(db, payload.ownerId)
    record = models.Inspection(
        **{INSPECTION_FIELDS[key]: value for key, value in payload.model_dump().items()}
    )
    db.add(record)
    _commit(db, f"Inspection code {payload.inspectionCode} already exists")
    db.refresh(record)
    return record


def get_inspections(db: Session, skip: int, limit: int):
    return (
        db.query(models.Inspection)
        .order_by(models.Inspection.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_inspections_naive(db: Session, limit: int):
    rows = db.query(models.Inspection).order_by(models.Inspection.id.asc()).limit(limit).all()
    result = []
    for row in rows:
        # one extra query per inspection -> 1 + N queries in total
        violations = (
            db.query(models.Violation).filter(models.Violation.inspection_id == row.id).all()
        )
        result.append((row, violations))
    return result


def get_inspections_fixed(db: Session, limit: int):
    # Eager loading - selectinload fetches all violations for these inspections in one extra IN (...) query
    return (
        db.query(models.Inspection)
        .options(selectinload(models.Inspection.violations))
        .order_by(models.Inspection.id.asc())
        .limit(limit)
        .all()
    )


def get_inspection(db: Session, inspection_id: int):
    record = db.get(models.Inspection, inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Inspection {inspection_id} not found")
    return record


def update_inspection(db: Session, inspection_id: int, payload: schema.InspectionUpdate):
    record = get_inspection(db, inspection_id)
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "ownerId" in data:
        get_owner(db, data["ownerId"])
    for key, value in data.items():
        setattr(record, INSPECTION_FIELDS[key], value)
    _commit(db, f"Inspection code {payload.inspectionCode} already exists")
    db.refresh(record)
    return record


def delete_inspection(db: Session, inspection_id: int):
    record = get_inspection(db, inspection_id)
    db.delete(record)
    db.commit()
