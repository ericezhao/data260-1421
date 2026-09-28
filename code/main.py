from pathlib import Path
import hashlib
import secrets

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import crud
import models
import schema
from database import Base, db_session_basede26, engine, get_db
from session_crud import create_session, delete_session, get_session

PORT_BASE = 8521
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend" / "dist"

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Local Restaurant Inspections")

# add middleware to allow requests from the frontend，for frontend development
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["http://localhost:5173"], # allow requests from the frontend
    allow_credentials=True, # allow credentials (cookies) to be sent with the request
    allow_methods=["*"], # allow all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # allow all headers 
)

# require_session must be defined before these Depends(...) lines
def require_session(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_id")
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")
    session_row = get_session(db, token)
    if not session_row:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return session_row


@app.post("/auth/login")
def login(payload: schema.LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    session_row = create_session(db, user_id=user.id)
    response.set_cookie(
        key="session_id",
        value=session_row.id,
        httponly=True,
        samesite="lax",
        max_age=30 * 60,
    )
    return {"message": "logged in", "userId": user.id}


@app.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("session_id")
    if token:
        delete_session(db, token)
    response.delete_cookie("session_id")
    return {"message": "logged out"}


@app.get("/auth/me")
def me(session_row=Depends(require_session)):
    return {"loggedIn": True, "userId": session_row.user_id}


@app.get("/api/inspections", response_model=list[schema.InspectionOut])
def list_inspections(
    db: Session = Depends(get_db),
    _session=Depends(require_session),
):
    return [inspection_out(row) for row in crud.get_inspections(db)]


@app.get("/api/inspections/{inspection_id}", response_model=schema.InspectionOut)
def get_inspection_api(
    inspection_id: int,
    db: Session = Depends(get_db),
    _session=Depends(require_session),
):
    row = crud.get_inspection(db, inspection_id)
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return inspection_out(row)


@app.post("/api/inspections", response_model=schema.InspectionOut, status_code=201)
def create_inspection_api(
    payload: schema.InspectionCreate,
    db: Session = Depends(get_db),
    _session=Depends(require_session),
):
    return inspection_out(crud.create_inspection(db, payload))


@app.put("/api/inspections/{inspection_id}", response_model=schema.InspectionOut)
def update_inspection_api(
    inspection_id: int,
    payload: schema.InspectionUpdate,
    db: Session = Depends(get_db),
    _session=Depends(require_session),
):
    row = crud.update_inspection(db, inspection_id, payload)
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return inspection_out(row)


@app.delete("/api/inspections/{inspection_id}", status_code=204)
def delete_inspection_api(
    inspection_id: int,
    db: Session = Depends(get_db),
    _session=Depends(require_session),
):
    row = crud.delete_inspection(db, inspection_id)
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return Response(status_code=204)


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
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 120000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 120000
    ).hex()
    return secrets.compare_digest(check, digest)


def seed_if_empty():
    db = db_session_basede26()
    try:
        email = "eric.zhao@sjsu.edu"
        user = db.query(models.User).filter(models.User.email == email).first()
        password_hash = hash_password("password")
        if user is None:
            db.add(
                models.User(
                    name="Eric Zhao",
                    email=email,
                    password_hash=password_hash,
                )
            )
        if db.query(models.Inspection).count() == 0:
            db.add(models.Inspection(restaurant_name="Torihide Yakitori", cuisine="Japanese"))
            db.add(models.Inspection(restaurant_name="Mission Steakhouse", cuisine="American"))
            db.add(models.Inspection(restaurant_name="Takeshi Sushi", cuisine="Japanese"))
        db.commit()
    finally:
        db.close()


def inspection_out(row: models.Inspection) -> schema.InspectionOut:
    return schema.InspectionOut(
        id=row.id,
        restaurantName=row.restaurant_name,
        cuisine=row.cuisine,
    )


seed_if_empty()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT_BASE)
