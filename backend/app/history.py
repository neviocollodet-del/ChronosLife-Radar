"""Conteggi storici da Hacker News (API Algolia, gratuita, senza chiave): numero di storie che citano una
parola chiave nella meta' recente e in quella precedente di ogni finestra. Fonte con storico profondo:
permette il Momentum fin dal primo giorno. Gli errori di rete non bloccano nulla."""
import json, time
from urllib.parse import urlencode

from .sectors import HN_SKIP, SECTORS

URL = "https://hn.algolia.com/api/v1/search?"


def hn_count(keyword: str, start: int, end: int, fetcher) -> int:
    q = urlencode({"query": f'"{keyword}"', "tags": "story", "hitsPerPage": 0,
                   "numericFilters": f"created_at_i>={start},created_at_i<{end}"})
    return int(json.loads(fetcher(URL + q))["nbHits"])


def collect(now: int, windows, fetcher, pause: float = 0.0):
    """Ritorna ({(settore, parola, giorni): (recenti, precedenti)}, {"ok": n, "errori": n})."""
    out, ok, errors = {}, 0, 0
    for sid, cfg in SECTORS.items():
        for kw in cfg["keywords"]:
            if kw in HN_SKIP:
                continue
            for days in windows:
                mid = now - (days * 86400) // 2
                try:
                    out[(sid, kw, days)] = (hn_count(kw, mid, now + 1, fetcher),
                                            hn_count(kw, now - days * 86400, mid, fetcher))
                    ok += 1
                except Exception:
                    errors += 1
                if pause:
                    time.sleep(pause)
    return out, {"ok": ok, "errori": errors}
