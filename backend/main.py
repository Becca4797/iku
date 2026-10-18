import logging
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# NOTE: the heavy modules (route_builder, store, scoring, ...) are imported
# inside the route handler below, not here. That keeps server start-up and
# --reload nearly instant. They load once, on the first route request.

app = FastAPI()
logger = logging.getLogger("uvicorn.error")


@app.exception_handler(Exception)
async def explain_unexpected_errors(request: Request, exc: Exception):
    """
    Catch-all: any crash (a failed import, the database, a bug) prints its
    full traceback in the terminal and sends a readable reason to the app,
    instead of a bare "Internal Server Error".
    """
    logger.error("Unhandled error on %s", request.url.path, exc_info=exc)
    first_line = (str(exc).strip().splitlines() or [""])[0][:200]
    return JSONResponse(
        status_code=500,
        content={"detail": f"Server error ({type(exc).__name__}): {first_line}"},
    )


class LatLng(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    start: LatLng
    destination: LatLng
    preference: Literal["safest", "balanced", "fastest"] = "balanced"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/routes")
async def routes(request: RouteRequest):
    """Build and score walking routes from start to destination."""
    # Imported here so the server starts fast (see note above).
    from config import LONDON
    from route_builder import build_routes
    from route_response import serialise_result

    try:
        result = await build_routes(
            start=(request.start.lat, request.start.lng),
            destination=(request.destination.lat, request.destination.lng),
            preference=request.preference,
            departure_time=datetime.now(LONDON),
        )
    except ValueError as exc:
        # e.g. start and destination are the same place
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Anything else (database down, bad data, a bug). Print the full
        # traceback in the terminal and send a readable reason to the app,
        # instead of a bare "500".
        logger.exception("Route request failed")
        first_line = (str(exc).strip().splitlines() or [""])[0][:200]
        raise HTTPException(
            status_code=500,
            detail=f"Route service error ({type(exc).__name__}): {first_line}",
        )

    return serialise_result(result)


# Serve the front end (must come after the API routes)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")