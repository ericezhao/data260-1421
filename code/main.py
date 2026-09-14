from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Query, Response
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

WEB_DIR = Path(__file__).resolve().parent / "web_application"
PORT_BASE = 8521

app = FastAPI(title="Local Restaurant Inspections")


class InspectionRecord(BaseModel):
    id: int
    restaurantName: str
    cuisine: str
    Email: str
    Comments: str
    Result: str
    termsAccepted: bool = False
    submissionDate: str = ""


class InspectionCreate(BaseModel):
    restaurantName: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)
    Email: str = Field(min_length=1)
    Comments: str = Field(min_length=1)
    Result: str = Field(min_length=1)
    termsAccepted: bool = False
    submissionDate: str = ""


class InspectionUpdate(BaseModel):
    restaurantName: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)


records: list[InspectionRecord] = [
    InspectionRecord(
        id=1,
        restaurantName="Torihide Yakitori",
        cuisine="Japanese",
        Email="eric.e.zhao@sjsu.edu",
        Comments="Raw shell eggs stored on the top shelf directly above ready-to-eat lettuce inside the walk-in cooler. Corrective action: Products rearranged by proper cooking temperature hierarchy. Hand sink near the dish station blocked by stacked milk crates and lacking hand soap and paper towels. Corrective action: Area cleared and restocked immediately.",
        Result="Needs Reinspection",
        termsAccepted=True,
        submissionDate="2026-09-01T18:00:00.000Z",
    ),
    InspectionRecord(
        id=2,
        restaurantName="Mission Steakhouse",
        cuisine="American",
        Email="eric.e.zhao@sjsu.edu",
        Comments="Handwash sink was stocked and food temperatures were within the required range.",
        Result="Pass",
        termsAccepted=True,
        submissionDate="2026-09-02T16:30:00.000Z",
    ),
     InspectionRecord(
        id=3,
        restaurantName="Takeshi Sushi",
        cuisine="Japanese",
        Email="eric.e.zhao@sjsu.edu",
        Comments="Observed approximately 5 live fruit flies near the mop sink and small-scale gnats around the bar drain.",
        Result="Fail",
        termsAccepted=True,
        submissionDate="2026-09-03T12:30:00.000Z",
    ),
]


def next_id() -> int:
    return max((record.id for record in records), default=0) + 1


def matching_records(query: str) -> list[InspectionRecord]:
    needle = query.strip().lower()
    if not needle:
        return list(records)
    return [
        record
        for record in records
        if needle in record.restaurantName.lower() or needle in record.cuisine.lower()
    ]


def add_record(payload: InspectionCreate) -> InspectionRecord:
    restaurant_name = payload.restaurantName.strip()
    cuisine = payload.cuisine.strip()
    email = payload.Email.strip()
    comments = payload.Comments.strip()
    result = payload.Result.strip()
    if not restaurant_name or not cuisine or not email or not comments or not result:
        raise HTTPException(status_code=400, detail="Restaurant name, cuisine, email, comments, and result are required")
    record = InspectionRecord(
        id=next_id(),
        restaurantName=restaurant_name,
        cuisine=cuisine,
        Email=email,
        Comments=comments,
        Result=result,
        termsAccepted=payload.termsAccepted,
        submissionDate=payload.submissionDate.strip(),
    )
    records.append(record)
    return record


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "web_app.html")


@app.get("/styles.css")
def styles():
    return FileResponse(WEB_DIR / "styles.css")


@app.get("/app.js")
def script():
    return FileResponse(WEB_DIR / "app.js")


@app.get("/api/records", response_model=list[InspectionRecord])
def list_records(
    response: Response,
    q: str = Query(default=""),
):
    response.headers["Cache-Control"] = "no-store"
    return matching_records(q)


@app.post("/api/records", response_model=InspectionRecord, status_code=201)
def create_record_api(payload: InspectionCreate):
    return add_record(payload)


@app.put("/api/records/1", response_model=InspectionRecord)
def update_record_one_api(payload: InspectionUpdate):
    restaurant_name = payload.restaurantName.strip()
    cuisine = payload.cuisine.strip()
    if not restaurant_name or not cuisine:
        raise HTTPException(status_code=400, detail="Restaurant name and cuisine are required")

    record = next((item for item in records if item.id == 1), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Record 1 was not found")

    record.restaurantName = restaurant_name
    record.cuisine = cuisine
    return record


@app.delete("/api/records/highest", status_code=204)
def delete_highest_record_api():
    if not records:
        raise HTTPException(status_code=404, detail="No records to delete")
    highest_id = max(record.id for record in records)
    records[:] = [record for record in records if record.id != highest_id]
    return Response(status_code=204)


@app.post("/records")
def create_record_form(
    restaurantName: str = Form(),
    cuisine: str = Form(),
    Email: str = Form(default=""),
    Comments: str = Form(default=""),
    Result: str = Form(default=""),
    termsAccepted: str = Form(default=""),
    submissionDate: str = Form(default=""),
):
    add_record(
        InspectionCreate(
            restaurantName=restaurantName,
            cuisine=cuisine,
            Email=Email,
            Comments=Comments,
            Result=Result,
            termsAccepted=bool(termsAccepted),
            submissionDate=submissionDate,
        )
    )
    return RedirectResponse(url="/", status_code=303)


@app.post("/records/1")
def update_record_one(
    restaurantName: str = Form(),
    cuisine: str = Form(),
):
    restaurantName = restaurantName.strip()
    cuisine = cuisine.strip()
    if not restaurantName or not cuisine:
        raise HTTPException(status_code=400, detail="Restaurant name and cuisine are required")

    record = next((item for item in records if item.id == 1), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Record 1 was not found")

    record.restaurantName = restaurantName
    record.cuisine = cuisine
    return RedirectResponse(url="/", status_code=303)


@app.post("/records/delete-highest")
def delete_highest_record():
    if not records:
        return RedirectResponse(url="/", status_code=303)
    highest_id = max(record.id for record in records)
    records[:] = [record for record in records if record.id != highest_id]
    return RedirectResponse(url="/", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT_BASE)
