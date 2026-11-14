"""Esecuzione giornaliera senza server (GitHub Actions): carica l'archivio, raccoglie dai feed,
salva l'archivio aggiornato e scrive i JSON dei trend letti dall'app.
Uso: python -m app.publish DIRECTORY_DATI"""
import json, sys, time
from pathlib import Path

from . import history, ingest, trends
from .sectors import SECTORS

WINDOWS = (30, 90, 365)
RETENTION_DAYS = 365
COLS = ("id", "sector_id", "source", "title", "summary", "link", "published")


def _load(db, f: Path):
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                db.execute("INSERT OR IGNORE INTO items VALUES(?,?,?,?,?,?,?)", [r[c] for c in COLS])
        db.commit()


def run(out_dir, now=None, fetcher=ingest.fetch, hn_fetcher=None):
    now = now or int(time.time())
    out = Path(out_dir)
    (out / "trends").mkdir(parents=True, exist_ok=True)
    db = ingest.connect(":memory:")
    _load(db, out / "items.jsonl")
    report = ingest.ingest_all(db, fetcher=fetcher, now=now, compact=True)
    rows = db.execute(f"SELECT {','.join(COLS)} FROM items WHERE published>=? ORDER BY published, id",
                      (now - RETENTION_DAYS * 86400,)).fetchall()
    (out / "items.jsonl").write_text(
        "".join(json.dumps(dict(zip(COLS, r)), ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    extra, hn_report = ({}, "non attivo")
    if hn_fetcher:
        extra, hn_report = history.collect(now, WINDOWS, hn_fetcher, pause=0.2)
    report["hackernews"] = hn_report
    for sid in SECTORS:
        for days in WINDOWS:
            data = trends.compute_trends(db, sid, days, now=now, extra=extra)
            (out / "trends" / f"{sid}-{days}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "status.json").write_text(json.dumps({"updated": now, "sources": report}, ensure_ascii=False, indent=1))
    return report


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], hn_fetcher=ingest.fetch), indent=2, ensure_ascii=False))
