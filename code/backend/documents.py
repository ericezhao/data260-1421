from fastapi import APIRouter, HTTPException, status
from pymongo.errors import PyMongoError

from mongo_db import ensure_collections, inspections
from mongo_schemas import InspectionDocCreate, InspectionDocOut, InspectionDocUpdate
from mongo_utils import is_valid_object_id, now_utc, serialize_inspection, to_object_id

router = APIRouter(prefix="/api/documents", tags=["Inspection documents"])


def _ready():
    try:
        ensure_collections()
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB is not available.")


@router.post("", response_model=InspectionDocOut, status_code=status.HTTP_201_CREATED)
def create_document(payload: InspectionDocCreate):
    _ready()
    col = inspections()
    doc = payload.model_dump(exclude_none=True)
    ts = now_utc()
    doc["createdAt"] = ts
    doc["updatedAt"] = ts
    try:
        res = col.insert_one(doc)
        created = col.find_one({"_id": res.inserted_id})
        return serialize_inspection(created)
    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database error while creating the document.")


@router.get("", response_model=list[InspectionDocOut])
def list_documents():
    _ready()
    col = inspections()
    try:
        docs = list(col.find().sort("createdAt", -1))
        return [serialize_inspection(doc) for doc in docs]
    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database error while listing documents.")


@router.get("/{doc_id}", response_model=InspectionDocOut)
def get_document(doc_id: str):
    if not is_valid_object_id(doc_id):
        raise HTTPException(status_code=400, detail="Invalid id format.")
    _ready()
    col = inspections()
    try:
        doc = col.find_one({"_id": to_object_id(doc_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        return serialize_inspection(doc)
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database error while fetching the document.")


@router.put("/{doc_id}", response_model=InspectionDocOut)
def update_document(doc_id: str, payload: InspectionDocUpdate):
    if not is_valid_object_id(doc_id):
        raise HTTPException(status_code=400, detail="Invalid id format.")
    _ready()
    col = inspections()
    try:
        existing = col.find_one({"_id": to_object_id(doc_id)})
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found.")
        updates = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields provided to update.")
        updates["updatedAt"] = now_utc()
        col.update_one({"_id": to_object_id(doc_id)}, {"$set": updates})
        updated = col.find_one({"_id": to_object_id(doc_id)})
        return serialize_inspection(updated)
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database error while updating the document.")


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: str):
    if not is_valid_object_id(doc_id):
        raise HTTPException(status_code=400, detail="Invalid id format.")
    _ready()
    col = inspections()
    try:
        res = col.delete_one({"_id": to_object_id(doc_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found.")
        return
    except HTTPException:
        raise
    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database error while deleting the document.")
