"""Raccolta da feed RSS/Atom -> SQLite. Solo libreria standard. Nessun contenuto inventato."""
import hashlib, re, sqlite3, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .sectors import SECTORS

SCHEMA = """CREATE TABLE IF NOT EXISTS items(
  id TEXT PRIMARY KEY, sector_id TEXT NOT NULL, source TEXT NOT NULL,
  title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', link TEXT NOT NULL DEFAULT '',
  published INTEGER NOT NULL)"""


def connect(path: str = "radar.db") -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute(SCHEMA)
    return db


def _strip(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(el) -> str:
    return re.sub(r"<[^>]+>", " ", "".join(el.itertext())).strip() if el is not None else ""


def _first(fields: dict, *names):
    for n in names:
        if fields.get(n) is not None:
            return fields[n]
    return None


def _parse_date(value: str, fallback: int) -> int:
    value = (value or "").strip()
    try:
        return int(parsedate_to_datetime(value).timestamp())
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return fallback


def parse_feed(xml_bytes: bytes, now: int):
    """Restituisce [{title, summary, link, published}] da RSS 2.0, Atom o RDF."""
    root = ET.fromstring(xml_bytes)
    out = []
    for el in root.iter():
        if _strip(el.tag) not in ("item", "entry"):
            continue
        f = {_strip(c.tag): c for c in el}
        link = ""
        if "link" in f:
            link = f["link"].get("href") or _text(f["link"])
        date = _text(_first(f, "pubDate", "published", "updated", "date"))
        title = _text(f.get("title"))
        if not title:
            continue
        out.append({"title": title,
                    "summary": _text(_first(f, "description", "summary", "content"))[:1000],
                    "link": link, "published": _parse_date(date, now)})
    return out


def store(db, sector_id: str, source: str, items) -> int:
    n = 0
    for it in items:
        iid = hashlib.sha1(f"{source}|{it['link'] or it['title']}".encode()).hexdigest()
        cur = db.execute("INSERT OR IGNORE INTO items VALUES(?,?,?,?,?,?,?)",
                         (iid, sector_id, source, it["title"], it["summary"], it["link"], it["published"]))
        n += cur.rowcount
    db.commit()
    return n


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ChronosLifeRadar/0.1 (personal)"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def ingest_all(db, fetcher=fetch, now=None):
    """Ritorna {fonte: nuovi_item | 'errore: ...'}. Una fonte che fallisce non blocca le altre."""
    now = now or int(time.time())
    report = {}
    for sid, cfg in SECTORS.items():
        for source, url in cfg["feeds"]:
            try:
                report[source] = store(db, sid, source, parse_feed(fetcher(url), now))
            except Exception as e:
                report[source] = f"errore: {e}"
    return report


if __name__ == "__main__":
    import json, sys
    print(json.dumps(ingest_all(connect(sys.argv[1] if len(sys.argv) > 1 else "radar.db")), indent=2, ensure_ascii=False))
