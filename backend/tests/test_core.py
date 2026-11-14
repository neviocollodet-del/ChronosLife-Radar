import time
from app import ingest, trends

NOW = 1_800_000_000
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>New AI agent framework</title><link>http://a/1</link>
<description>&lt;p&gt;An agentic workflow with RAG&lt;/p&gt;</description>
<pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Warehouse automation grows</title><link>http://a/2</link><description>x</description></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>AI agent paper</title>
<link href="http://b/1"/><updated>2026-11-12T08:00:00Z</updated><summary>reasoning models</summary></entry></feed>"""


def test_parse_rss_and_atom():
    r = ingest.parse_feed(RSS, NOW)
    assert [i["title"] for i in r] == ["New AI agent framework", "Warehouse automation grows"]
    assert "<p>" not in r[0]["summary"] and r[0]["link"] == "http://a/1"
    assert r[0]["published"] == 1_794_564_000  # 13 nov 2026 10:00 UTC, letta dal feed
    assert "agentic workflow" in r[0]["summary"]
    assert r[1]["published"] == NOW  # data mancante -> fallback dichiarato
    a = ingest.parse_feed(ATOM, NOW)
    assert a[0]["link"] == "http://b/1" and a[0]["published"] > 1_700_000_000


def test_store_is_idempotent():
    db = ingest.connect(":memory:")
    items = ingest.parse_feed(RSS, NOW)
    assert ingest.store(db, "ai-tech", "s1", items) == 2
    assert ingest.store(db, "ai-tech", "s1", items) == 0


def test_trends_count_sources_and_window():
    db = ingest.connect(":memory:")
    n = int(time.mktime((2026, 11, 14, 0, 0, 0, 0, 0, 0)))
    ingest.store(db, "ai-tech", "s1", ingest.parse_feed(RSS, n))
    ingest.store(db, "ai-tech", "s2", ingest.parse_feed(ATOM, n))
    t = trends.compute_trends(db, "ai-tech", 90, now=n)
    top = {i["topic"]: i for i in t["items"]}
    assert top["AI agent"]["evidence_count"] == 2
    assert top["AI agent"]["independent_source_labels"] == 2
    assert t["data_status"] == "insufficient"  # < 20 item: nessuna conclusione
    assert all(i["momentum"] is None for i in t["items"])  # 2 evidenze: troppo poche
    assert trends.compute_trends(db, "ai-tech", 1, now=n + 400 * 86400)["items"] == []


def test_ingest_all_survives_failing_feed():
    db = ingest.connect(":memory:")
    def fetcher(url):
        if "arxiv" in url:
            raise OSError("down")
        return RSS
    rep = ingest.ingest_all(db, fetcher=fetcher, now=NOW)
    assert rep["arxiv-cs-ai"].startswith("errore")
    assert isinstance(rep["huggingface-blog"], int)


def _mk(db, source, n_recent, n_prev, now, kw="AI agent"):
    items = [{"title": f"{kw} r{i}", "summary": "", "link": f"{source}/r{i}", "published": now - 86400} for i in range(n_recent)]
    items += [{"title": f"{kw} p{i}", "summary": "", "link": f"{source}/p{i}", "published": now - 80 * 86400} for i in range(n_prev)]
    ingest.store(db, "ai-tech", source, items)


def test_momentum_formula_and_thresholds():
    db = ingest.connect(":memory:")
    _mk(db, "s1", 4, 1, NOW)
    _mk(db, "s2", 3, 0, NOW)
    t = {i["topic"]: i for i in trends.compute_trends(db, "ai-tech", 90, now=NOW)["items"]}["AI agent"]
    assert (t["recent_count"], t["previous_count"]) == (7, 1)
    assert t["momentum"] == 75 and t["score_status"] == "ok"   # (7-1)/8*100
    db2 = ingest.connect(":memory:")
    _mk(db2, "s1", 6, 0, NOW)  # una sola fonte: niente score
    t2 = trends.compute_trends(db2, "ai-tech", 90, now=NOW)["items"][0]
    assert t2["momentum"] is None and t2["score_status"] == "dati insufficienti"
