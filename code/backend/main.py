import json
from pathlib import Path

import crud
import models
import schema
import uvicorn
from bike_api import router as bike_router
from chat_api import router as chat_router
from database import Base, db_session_basede26, engine, get_db, sql_counter
from dependencies import get_current_user, require_roles
from documents import router as documents_router
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from security import create_access_token, get_password_hash, verify_password
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

PORT_BASE = 8521
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Local Restaurant Inspections")

# add middleware to allow requests from the frontend，for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # allow requests from the frontend
    allow_credentials=True,  # allow credentials (cookies) to be sent with the request
    allow_methods=["*"],  # allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # allow all headers
)


# count SQL statements per request and return the number in the X-SQL-Count header
@app.middleware("http")
async def count_sql_statements(request: Request, call_next):
    counter = [0]
    token = sql_counter.set(counter)
    try:
        response = await call_next(request)
    finally:
        sql_counter.reset(token)
    response.headers["X-SQL-Count"] = str(counter[0])
    return response


@app.middleware("http")
async def reject_invalid_json(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH"}:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            raw = await request.body()
            if raw:
                try:
                    json.loads(raw)
                except json.JSONDecodeError:
                    return JSONResponse(
                        status_code=400, content={"detail": "Request body is not valid JSON."}
                    )
    return await call_next(request)


# ----- JWT authentication -----
@app.post("/auth/login", response_model=schema.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schema.AuthMeOut)
def me(current_user: models.User = Depends(get_current_user)):
    return schema.AuthMeOut(
        id=current_user.id,
        username=current_user.username,
        name=current_user.name,
        role=current_user.role,
    )


# ----- owners -----
@app.post("/api/owners", response_model=schema.OwnerOut, status_code=201)
def create_owner_api(
    payload: schema.OwnerCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(["writer", "moderator"])),
):
    return owner_out(crud.create_owner(db, payload))


@app.get("/api/owners", response_model=list[schema.OwnerOut])
def list_owners(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return [owner_out(row) for row in crud.get_owners(db, skip, limit)]


@app.get("/api/owners/{owner_id}", response_model=schema.OwnerOut)
def get_owner_api(
    owner_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return owner_out(crud.get_owner(db, owner_id))


@app.put("/api/owners/{owner_id}", response_model=schema.OwnerOut)
def update_owner_api(
    owner_id: int,
    payload: schema.OwnerUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(["writer", "moderator"])),
):
    return owner_out(crud.update_owner(db, owner_id, payload))


@app.delete("/api/owners/{owner_id}", status_code=204)
def delete_owner_api(
    owner_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(["moderator"])),
):
    crud.delete_owner(db, owner_id)
    return Response(status_code=204)


@app.get("/api/owners/{owner_id}/inspections", response_model=list[schema.InspectionOut])
def list_owner_inspections(
    owner_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return [inspection_out(row) for row in crud.get_inspections_by_owner(db, owner_id, skip, limit)]


# ----- inspections -----
@app.get("/api/inspections", response_model=list[schema.InspectionOut])
def list_inspections(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return [inspection_out(row) for row in crud.get_inspections(db, skip, limit)]


# must stay above /api/inspections/{inspection_id}, otherwise "naive" is parsed as an id
@app.get("/api/inspections/naive", response_model=list[schema.InspectionWithViolations])
def list_inspections_naive(
    limit: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return [
        inspection_with_violations(row, violations)
        for row, violations in crud.get_inspections_naive(db, limit)
    ]


@app.get("/api/inspections/fixed", response_model=list[schema.InspectionWithViolations])
def list_inspections_fixed(
    limit: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return [
        inspection_with_violations(row, row.violations)
        for row in crud.get_inspections_fixed(db, limit)
    ]


@app.get("/api/inspections/{inspection_id}", response_model=schema.InspectionOut)
def get_inspection_api(
    inspection_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return inspection_out(crud.get_inspection(db, inspection_id))


@app.post("/api/inspections", response_model=schema.InspectionOut, status_code=201)
def create_inspection_api(
    payload: schema.InspectionCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(["writer", "moderator"])),
):
    return inspection_out(crud.create_inspection(db, payload))


@app.put("/api/inspections/{inspection_id}", response_model=schema.InspectionOut)
def update_inspection_api(
    inspection_id: int,
    payload: schema.InspectionUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(["writer", "moderator"])),
):
    return inspection_out(crud.update_inspection(db, inspection_id, payload))


@app.delete("/api/inspections/{inspection_id}", status_code=204)
def delete_inspection_api(
    inspection_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(["moderator"])),
):
    crud.delete_inspection(db, inspection_id)
    return Response(status_code=204)


app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(bike_router)

if FRONTEND_DIR.exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def home_page():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        return FileResponse(FRONTEND_DIR / "index.html")


# ----- helper functions -----
def ensure_user_columns() -> None:
    """Add HW7 username/role columns when the HW4 users table is still present."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "username" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(80) NULL"))
            conn.execute(text("CREATE UNIQUE INDEX uq_users_username ON users (username)"))
        if "role" not in columns:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL " "DEFAULT 'reader'")
            )


def seed_if_empty():
    ensure_user_columns()
    db = db_session_basede26()
    try:
        role_users = [
            ("reader", "reader123", "reader", "Reader User", "reader@example.com"),
            ("writer", "writer123", "writer", "Writer User", "writer@example.com"),
            (
                "moderator",
                "moderator123",
                "moderator",
                "Moderator User",
                "moderator@example.com",
            ),
        ]
        for username, password, role, name, email in role_users:
            row = db.query(models.User).filter(models.User.username == username).first()
            if row is None:
                db.add(
                    models.User(
                        name=name,
                        email=email,
                        username=username,
                        password_hash=get_password_hash(password),
                        role=role,
                    )
                )
            else:
                row.role = role
                row.password_hash = get_password_hash(password)
        if db.query(models.Inspection).count() == 0:
            owner = models.Owner(
                name="Maria Lopez",
                phone="408-555-0101",
                email="maria.lopez@example.com",
            )
            db.add(owner)
            db.flush()
            samples = [
                ("Torihide Yakitori", "Japanese"),
                ("Mission Steakhouse", "American"),
                ("Takeshi Sushi", "Japanese"),
            ]
            for i, (name, cuisine) in enumerate(samples, start=1):
                db.add(
                    models.Inspection(
                        restaurant_name=name,
                        cuisine=cuisine,
                        inspection_code=f"INS-{i:05d}",
                        owner_id=owner.id,
                    )
                )
        db.commit()
    finally:
        db.close()


def owner_out(row: models.Owner) -> schema.OwnerOut:
    return schema.OwnerOut(
        id=row.id,
        name=row.name,
        phone=row.phone,
        email=row.email,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


def inspection_fields(row: models.Inspection) -> dict:
    return {
        "id": row.id,
        "restaurantName": row.restaurant_name,
        "cuisine": row.cuisine,
        "inspectionCode": row.inspection_code,
        "score": row.score,
        "ownerId": row.owner_id,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


def inspection_out(row: models.Inspection) -> schema.InspectionOut:
    return schema.InspectionOut(**inspection_fields(row))


def inspection_with_violations(row, violations) -> schema.InspectionWithViolations:
    return schema.InspectionWithViolations(
        **inspection_fields(row),
        violations=[
            schema.ViolationOut(id=v.id, description=v.description, severity=v.severity)
            for v in violations
        ],
    )


seed_if_empty()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT_BASE)
