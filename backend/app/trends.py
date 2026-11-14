"""Aggregazione evidenze per settore. Momentum Score = variazione tra meta' recente e meta' precedente della finestra,
calcolato solo con evidenze e fonti sufficienti; altrimenti None (PRD: niente previsioni senza dati)."""
import re, time

from .sectors import SECTORS

MIN_ITEMS_FOR_OK = 20
MIN_EVIDENCE_FOR_SCORE = 5   # evidenze minime (recenti + precedenti) per calcolare il Momentum
MIN_SOURCES_FOR_SCORE = 2    # fonti distinte minime


def _pattern(keyword: str):
    return re.compile(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", re.IGNORECASE)


def compute_trends(db, sector_id: str, window_days: int, now=None, limit: int = 20):
    cfg = SECTORS[sector_id]
    now = now or int(time.time())
    since = now - window_days * 86400
    mid = now - (window_days * 86400) // 2   # meta' recente / meta' precedente della finestra
    rows = db.execute("SELECT source, title, summary, published FROM items WHERE sector_id=? AND published>=?",
                      (sector_id, since)).fetchall()
    items = []
    for kw in cfg["keywords"]:
        pat = _pattern(kw)
        hits = [r for r in rows if pat.search(r[1] + " " + r[2])]
        if hits:
            sources = len({h[0] for h in hits})
            recent = sum(1 for h in hits if h[3] >= mid)
            previous = len(hits) - recent
            ok = len(hits) >= MIN_EVIDENCE_FOR_SCORE and sources >= MIN_SOURCES_FOR_SCORE
            # Momentum = (recenti - precedenti) / (recenti + precedenti) * 100, tra -100 e +100
            momentum = round(100 * (recent - previous) / len(hits)) if ok else None
            items.append({"topic": kw, "evidence_count": len(hits),
                          "independent_source_labels": sources,
                          "recent_count": recent, "previous_count": previous,
                          "momentum": momentum,
                          "score_status": "ok" if ok else "dati insufficienti"})
    items.sort(key=lambda x: (-x["evidence_count"], x["topic"]))
    return {"sector_id": sector_id, "window_days": window_days,
            "data_status": "ok" if len(rows) >= MIN_ITEMS_FOR_OK else "insufficient",
            "items_scanned": len(rows), "items": items[:limit]}
