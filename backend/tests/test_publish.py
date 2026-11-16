import json
from app import publish

NOW = 1_800_000_000
RSS = ("""<rss><channel><item><title>AI agent news</title><link>http://a/1</link><description>x</description>
<pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Unrelated cooking story</title><link>http://a/2</link><description>pasta</description></item>
</channel></rss>""").encode()


def test_publish_writes_files_and_is_idempotent(tmp_path):
    fetcher = lambda url: RSS
    publish.run(tmp_path, now=NOW, fetcher=fetcher)
    lines = (tmp_path / "items.jsonl").read_text().splitlines()
    assert all("cooking" not in l for l in lines) and len(lines) >= 1
    for sid in ("ai-tech", "operations", "sport"):
        for d in (30, 90, 365):
            j = json.loads((tmp_path / "trends" / f"{sid}-{d}.json").read_text())
            assert {"items", "data_status", "window_days"} <= set(j)
    first = (tmp_path / "items.jsonl").read_text()
    publish.run(tmp_path, now=NOW, fetcher=fetcher)
    assert (tmp_path / "items.jsonl").read_text() == first   # nessun doppione
    assert json.loads((tmp_path / "status.json").read_text())["updated"] == NOW


def test_publish_survives_all_feeds_down(tmp_path):
    def down(url): raise OSError("offline")
    rep = publish.run(tmp_path, now=NOW, fetcher=down)
    assert all(str(v).startswith("errore") for k, v in rep.items() if k not in ("hackernews", "visioni"))
    assert (tmp_path / "trends" / "ai-tech-90.json").exists()
