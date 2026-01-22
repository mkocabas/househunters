"""
HouseHunters v2 - FastAPI Backend
"""
import csv
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from zillow import parse_bounds_from_url, search_properties_async

app = FastAPI(title="HouseHunters", version="2.0.0")

# Setup static files and templates
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Data directory for saved searches
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class SearchRequest(BaseModel):
    zillow_url: str
    search_type: str = "sale"  # "sale" or "rent"
    min_beds: int | None = None
    max_beds: int | None = None
    min_baths: int | None = None
    max_baths: int | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_year: int | None = None
    max_year: int | None = None
    property_types: dict[str, bool] = {}


class ExportRequest(BaseModel):
    results: list[dict[str, Any]]
    format: str = "json"  # "json" or "csv"
    columns: list[str] = []


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/search")
async def search(request: SearchRequest):
    """Search properties on Zillow."""
    # Parse bounds from URL
    bounds = parse_bounds_from_url(request.zillow_url)
    if not bounds:
        raise HTTPException(
            status_code=400,
            detail="Could not parse map bounds from the Zillow URL. Please ensure it's a valid Zillow search URL.",
        )

    # Build filters
    filters = {
        "min_beds": request.min_beds,
        "max_beds": request.max_beds,
        "min_baths": request.min_baths,
        "max_baths": request.max_baths,
        "min_price": request.min_price,
        "max_price": request.max_price,
        "min_year": request.min_year,
        "max_year": request.max_year,
        "property_types": request.property_types,
    }

    try:
        results = await search_properties_async(bounds, filters, request.search_type)

        # Save results to disk
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"search_{request.search_type}_{timestamp}.json"
        filepath = DATA_DIR / filename

        save_data = {
            "search_type": request.search_type,
            "filters": filters,
            "bounds": bounds,
            "timestamp": timestamp,
            "results": results,
        }

        with open(filepath, "w") as f:
            json.dump(save_data, f, indent=2)

        return {
            "success": True,
            "count": len(results.get("listResults", [])),
            "results": results.get("listResults", []),
            "saved_to": filename,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export")
async def export_results(request: ExportRequest):
    """Export results as JSON or CSV."""
    if request.format == "csv":
        # Create CSV in memory
        output = io.StringIO()
        if request.results:
            # Use specified columns or extract all keys from first result
            if request.columns:
                fieldnames = request.columns
            else:
                fieldnames = list(request.results[0].keys())

            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for row in request.results:
                # Flatten nested data
                flat_row = flatten_dict(row)
                writer.writerow({k: flat_row.get(k, "") for k in fieldnames})

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=properties.csv"},
        )
    else:
        # JSON export
        return JSONResponse(
            content=request.results,
            headers={"Content-Disposition": "attachment; filename=properties.json"},
        )


def flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


@app.get("/api/saved-searches")
async def list_saved_searches():
    """List all saved search files."""
    files = sorted(DATA_DIR.glob("search_*.json"), reverse=True)
    return [
        {
            "filename": f.name,
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        }
        for f in files[:20]  # Last 20 searches
    ]


@app.get("/api/saved-searches/{filename}")
async def get_saved_search(filename: str):
    """Get a specific saved search."""
    filepath = DATA_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Search not found")

    with open(filepath) as f:
        return json.load(f)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
