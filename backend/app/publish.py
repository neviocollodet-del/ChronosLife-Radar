"""Esecuzione giornaliera senza server (GitHub Actions): carica l'archivio, raccoglie dai feed,
salva l'archivio aggiornato e scrive i JSON dei trend letti dall'app.
Uso: python -m app.publish DIRECTORY_DATI"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

from . import history, ingest, links, trends, verify, visions
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


def run(out_dir, now=None, fetcher=ingest.fetch, hn_fetcher=None, gemini_call=None):
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
    all_trends = {}
    for sid in SECTORS:
        for days in WINDOWS:
            data = trends.compute_trends(db, sid, days, now=now, extra=extra)
            all_trends[(sid, days)] = data
            (out / "trends" / f"{sid}-{days}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    _publish_visions(db, out, now, all_trends, gemini_call, report)
    (out / "links.json").write_text(json.dumps(links.compute_links(db, now), ensure_ascii=False, indent=1))
    (out / "status.json").write_text(json.dumps({"updated": now, "sources": report}, ensure_ascii=False, indent=1))
    return report


def _publish_visions(db, out, now, all_trends, gemini_call, report):
    vdir = out / "visions"
    vdir.mkdir(exist_ok=True)
    today = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
    t30 = {sid: all_trends[(sid, 30)] for sid in SECTORS}
    cands = visions.pick_candidates({sid: all_trends[(sid, 90)] for sid in SECTORS})
    day = []
    for c in cands:
        it = dict(c["item"])
        it["evidence_30"] = {i["topic"]: i["evidence_count"] for i in t30[c["sector_id"]]["items"]}.get(it["topic"], 0)
        src = visions.evidence_for(db, c["sector_id"], it["topic"], now)
        day.append(visions.make_vision(c["sector_id"], it, src, gemini_call))
    payload = {"date": today, "generated_by": "gemini" if any(v["generated_by"] == "gemini" for v in day) else "regole",
               "visions": day}
    (vdir / f"{today}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "visions" / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    by_date = {p.stem: json.loads(p.read_text(encoding="utf-8"))["visions"]
               for p in sorted(vdir.glob("????-??-??.json"))}
    index = [{"date": d, "headlines": [v["headline"] for v in vs]} for d, vs in sorted(by_date.items(), reverse=True)][:120]
    (vdir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    vf = out / "verification.json"
    existing = json.loads(vf.read_text()) if vf.exists() else {}
    vf.write_text(json.dumps(verify.update(existing, by_date, t30, today, now), ensure_ascii=False, indent=1))
    report["visioni"] = {"gemini": sum(v["generated_by"] == "gemini" for v in day),
                         "regole": sum(v["generated_by"] == "regole" for v in day)}


if __name__ == "__main__":
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    print(json.dumps(run(sys.argv[1], hn_fetcher=ingest.fetch, gemini_call=visions.make_gemini_call(key) if key else None), indent=2, ensure_ascii=False))
