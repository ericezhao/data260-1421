"""Routes for the Bay Wheels advisor page."""

import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from bike_share.agent import run_bike_agent
from bike_share.pipeline import run_pipeline

router = APIRouter(tags=["Bike share"])
UI = Path(__file__).resolve().parent / "bike_ui.html"
RAW = ROOT / "reports" / "hw07" / "raw" / "bike"

SCENARIOS = {
    "membership": {
        "csv": RAW / "membership_wins.csv",
        "fixture": RAW / "baywheels_pricing_membership.html",
    },
    "payg": {
        "csv": RAW / "payg_wins.csv",
        "fixture": RAW / "baywheels_pricing_payg.html",
    },
}


@router.get("/bike-ui")
def bike_page():
    return FileResponse(UI)


@router.post("/api/bike/run")
async def bike_run(
    scenario: str = Form("membership"),
    pricing_url: str = Form("https://www.lyft.com/bikes/bay-wheels/pricing"),
    mode: str = Form("react"),
    csv: UploadFile | None = File(None),
):
    spec = SCENARIOS.get(scenario, SCENARIOS["membership"])
    fixture = spec["fixture"].read_text(encoding="utf-8") if spec["fixture"].exists() else None
    if csv is not None:
        raw = await csv.read()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as handle:
            handle.write(raw)
            csv_path = Path(handle.name)
    else:
        csv_path = spec["csv"]

    # Prefer the ReAct loop; fall back if the model never returns a decision.
    if mode == "pipeline":
        result = run_pipeline(csv_path, pricing_url=pricing_url, fixture_text=fixture)
        result["runner"] = "pipeline"
        return result

    try:
        result = run_bike_agent(csv_path, pricing_url=pricing_url, fixture_text=fixture)
    except Exception as exc:
        result = run_pipeline(csv_path, pricing_url=pricing_url, fixture_text=fixture)
        result["runner"] = "pipeline_fallback"
        result["agent_error"] = f"{type(exc).__name__}: {exc}"
        return result

    if not result.get("decision"):
        fallback = run_pipeline(csv_path, pricing_url=pricing_url, fixture_text=fixture)
        fallback["runner"] = "pipeline_fallback"
        fallback["agent_metrics"] = result.get("metrics")
        fallback["agent_timeline"] = result.get("timeline")
        return fallback

    result["runner"] = "react"
    return result
