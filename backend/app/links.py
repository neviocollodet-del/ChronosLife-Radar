"""Collegamenti tra argomenti: quante notizie citano due parole chiave insieme (ultimi 90 giorni)."""
from itertools import combinations

from .sectors import SECTORS
from .trends import matched_keywords


def compute_links(db, now: int, days: int = 90, top: int = 25):
    out = {}
    for sid in SECTORS:
        rows = db.execute("SELECT title, summary FROM items WHERE sector_id=? AND published>=?",
                          (sid, now - days * 86400)).fetchall()
        counts = {}
        for title, summary in rows:
            kws = sorted(set(matched_keywords(sid, title + " " + summary)))
            for a, b in combinations(kws, 2):
                counts[(a, b)] = counts.get((a, b), 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
        out[sid] = [{"a": a, "b": b, "count": c} for (a, b), c in ranked]
    return out
