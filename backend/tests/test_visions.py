import json
from app import ingest, links, publish, verify, visions

NOW = 1_800_000_000


def _item(topic, rec, prev, srcs=2, mom=50):
    return {"topic": topic, "evidence_count": rec + prev, "independent_source_labels": srcs,
            "recent_count": rec, "previous_count": prev, "momentum": mom,
            "score_status": "ok" if mom is not None else "dati insufficienti"}


def test_pick_candidates_prefers_positive_momentum():
    t = {"ai-tech": {"items": [_item("a", 1, 9, mom=-80), _item("b", 9, 1, mom=80), _item("c", 5, 4, mom=11),
                               _item("d", 2, 0, srcs=1, mom=None)]}}
    c = visions.pick_candidates(t, per_sector=2)
    assert [x["item"]["topic"] for x in c] == ["b", "c"]
    t["ai-tech"]["items"] = [_item("d", 2, 0, srcs=1, mom=None)]
    assert visions.pick_candidates(t)[0]["item"]["topic"] == "d"   # senza score: propone comunque il segnale debole


def test_rule_vision_is_honest():
    v = visions.make_vision("ai-tech", _item("AI agent", 9, 1), [{"source": "s", "title": "t", "link": "http://x"}])
    assert v["generated_by"] == "regole" and v["confidence"] == "media"
    assert "previsione" in v["hypotheses"][0] and v["limits"] and v["sources"][0]["link"] == "http://x"
    w = visions.make_vision("ai-tech", _item("x", 2, 0, srcs=1, mom=None), [])
    assert w["confidence"] == "bassa"


def test_gemini_used_when_valid_and_fallback_when_not():
    good = json.dumps({"headline": "Titolo", "facts": ["f"], "hypotheses": ["h"],
                       "scenarios": [{"label": "A", "text": "t"}], "limits": "l"})
    v = visions.make_vision("ai-tech", _item("AI agent", 9, 1), [], gemini_call=lambda p: "```json\n" + good + "\n```")
    assert v["generated_by"] == "gemini" and v["headline"] == "Titolo"
    for bad in (lambda p: "non json", lambda p: '{"headline": 3}', lambda p: (_ for _ in ()).throw(OSError("rete"))):
        assert visions.make_vision("ai-tech", _item("AI agent", 9, 1), [], gemini_call=bad)["generated_by"] == "regole"


def test_prompt_contains_only_our_data():
    seen = []
    visions.make_vision("ai-tech", _item("AI agent", 9, 1), [{"source": "s", "title": "Titolo reale", "link": "l"}],
                        gemini_call=lambda p: seen.append(p) or "x")
    assert "Titolo reale" in seen[0] and "USA SOLO i dati" in seen[0]


def test_links_counts_cooccurrence():
    db = ingest.connect(":memory:")
    ingest.store(db, "ai-tech", "s", [{"title": "AI agent with RAG and agentic design", "summary": "", "link": "1", "published": NOW - 86400},
                                      {"title": "AI agent and agentic", "summary": "", "link": "2", "published": NOW - 86400}], compact=True)
    l = {(x["a"], x["b"]): x["count"] for x in links.compute_links(db, NOW)["ai-tech"]}
    assert l[("AI agent", "agentic")] == 2 and l[("AI agent", "RAG")] == 1


def test_verify_outcomes_and_idempotence():
    assert verify.outcome(10, 12) == "up" and verify.outcome(10, 10) == "flat" and verify.outcome(10, 5) == "down"
    assert verify.outcome(0, 5) == "up" and verify.outcome(0, 1) == "flat"
    v = {"sector_id": "ai-tech", "topic": "x", "baseline": {"momentum": 40, "evidence_30": 10}}
    weak = {"sector_id": "ai-tech", "topic": "y", "baseline": {"momentum": None, "evidence_30": 4}}
    by = {"2026-10-01": [v, weak]}
    t30 = {"ai-tech": {"items": [{"topic": "x", "evidence_count": 20}]}}
    r = verify.update({}, by, t30, "2026-11-14", NOW)            # 44 giorni: vale l'orizzonte 30, non il 90
    assert r["checked"] == 1 and r["confirmed"] == 1 and r["items"][0]["horizon_days"] == 30
    r2 = verify.update(r, by, t30, "2026-11-14", NOW)
    assert r2["checked"] == 1                                       # nessun doppione
    r3 = verify.update(r2, by, t30, "2026-12-31", NOW)              # ora anche 90 giorni
    assert r3["checked"] == 2


def test_publish_writes_visions_archive_links_verification(tmp_path):
    rss = ("<rss><channel>" + "".join(
        f"<item><title>AI agent story {i}</title><link>http://a/{i}</link><description>agentic</description>"
        f"<pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate></item>" for i in range(8)) + "</channel></rss>").encode()
    now = 1_794_650_000
    publish.run(tmp_path, now=now, fetcher=lambda u: rss)
    latest = json.loads((tmp_path / "visions" / "latest.json").read_text())
    assert latest["visions"] and latest["visions"][0]["sources"]
    idx = json.loads((tmp_path / "visions" / "index.json").read_text())
    assert idx[0]["date"] == latest["date"]
    assert (tmp_path / "links.json").exists() and (tmp_path / "verification.json").exists()
    st = json.loads((tmp_path / "status.json").read_text())["sources"]["visioni"]
    assert st["regole"] >= 1 and st["gemini"] == 0
    publish.run(tmp_path, now=now, fetcher=lambda u: rss)           # secondo giro nello stesso giorno: sovrascrive
    assert len(json.loads((tmp_path / "visions" / "index.json").read_text())) == 1
