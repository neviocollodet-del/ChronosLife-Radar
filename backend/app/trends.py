"""Aggregazione evidenze per settore. Nessun Momentum Score in questa versione: viene dichiarato
'non disponibile' finche' non esiste storico sufficiente (PRD: niente previsioni senza dati)."""
import re, time

from .sectors import SECTORS

MIN_ITEMS_FOR_OK = 20


def _pattern(keyword: str):
    return re.compile(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", re.IGNORECASE)


def compute_trends(db, sector_id: str, window_days: int, now=None, limit: int = 20):
    cfg = SECTORS[sector_id]
    now = now or int(time.time())
    since = now - window_days * 86400
    rows = db.execute("SELECT source, title, summary FROM items WHERE sector_id=? AND published>=?",
                      (sector_id, since)).fetchall()
    items = []
    for kw in cfg["keywords"]:
        pat = _pattern(kw)
        hits = [r for r in rows if pat.search(r[1] + " " + r[2])]
        if hits:
            items.append({"topic": kw, "evidence_count": len(hits),
                          "independent_source_labels": len({h[0] for h in hits}),
                          "score_status": "non disponibile"})
    items.sort(key=lambda x: (-x["evidence_count"], x["topic"]))
    return {"sector_id": sector_id, "window_days": window_days,
            "data_status": "ok" if len(rows) >= MIN_ITEMS_FOR_OK else "insufficient",
            "items_scanned": len(rows), "items": items[:limit]}
