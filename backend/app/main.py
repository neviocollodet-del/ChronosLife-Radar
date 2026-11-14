import os
from fastapi import FastAPI, HTTPException, Query

from . import ingest, trends
from .sectors import SECTORS

DB_PATH = os.environ.get("RADAR_DB", "radar.db")
app = FastAPI(title="ChronosLife Radar", version="0.2.0")


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/v1/sectors")
def sectors():
    return [{"id": k, "name": v["name"]} for k, v in SECTORS.items()]


@app.get("/v1/trends")
def get_trends(sector_id: str, window_days: int = Query(90, ge=1, le=730)):
    if sector_id not in SECTORS:
        raise HTTPException(404, "settore sconosciuto")
    db = ingest.connect(DB_PATH)
    try:
        return trends.compute_trends(db, sector_id, window_days)
    finally:
        db.close()


@app.post("/v1/ingest")
def run_ingest():
    db = ingest.connect(DB_PATH)
    try:
        return ingest.ingest_all(db)
    finally:
        db.close()
