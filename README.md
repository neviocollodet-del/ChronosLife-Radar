# ChronosLife-Radar

## Backend (M1 – raccolta evidenze)
FastAPI in `backend/`, contratto usato dall'app: `GET /v1/trends?sector_id=&window_days=`.

    cd backend && pip install -r requirements.txt
    python -m pytest -q
    python -m app.ingest            # raccoglie dai feed gratuiti in radar.db
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Settori, parole chiave e feed: `backend/app/sectors.py`. Momentum Score (M2): (evidenze recenti - precedenti) / totale x 100 su due meta' della finestra; `null` sotto 5 evidenze o 2 fonti.
Emulatore Android: 10.0.2.2:8000; telefono: IP LAN del PC.
