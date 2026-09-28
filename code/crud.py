from sqlalchemy.orm import Session

import models
import schema


def create_inspection(db: Session, payload: schema.InspectionCreate):
    record = models.Inspection(
        restaurant_name=payload.restaurantName,
        cuisine=payload.cuisine,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_inspections(db: Session):
    return db.query(models.Inspection).order_by(models.Inspection.id.asc()).all()


def get_inspection(db: Session, inspection_id: int):
    return db.query(models.Inspection).filter(models.Inspection.id == inspection_id).first()


def update_inspection(db: Session, inspection_id: int, payload: schema.InspectionUpdate):
    record = get_inspection(db, inspection_id)
    if not record:
        return None
    record.restaurant_name = payload.restaurantName
    record.cuisine = payload.cuisine
    db.commit()
    db.refresh(record)
    return record


def delete_inspection(db: Session, inspection_id: int):
    record = get_inspection(db, inspection_id)
    if not record:
        return None
    db.delete(record)
    db.commit()
    return record
