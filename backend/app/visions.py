"""Visioni giornaliere: candidati scelti dai numeri, testo scritto da Gemini (gratuito) o, in mancanza,
da regole fisse. Le fonti allegate vengono SEMPRE dai nostri dati, mai dal modello."""
import json, os, re, time, urllib.request

from .sectors import SECTORS

HALF = {30: 15, 90: 45, 365: 182}


def pick_candidates(trends90: dict, per_sector: int = 2):
    """Per ogni settore: prima i Momentum positivi piu' alti, poi (se mancano) gli argomenti con piu' evidenze."""
    out = []
    for sid, t in trends90.items():
        items = t["items"]
        scored = sorted([i for i in items if i["momentum"] is not None and i["momentum"] > 0],
                        key=lambda i: (-i["momentum"], -i["evidence_count"]))
        weak = sorted([i for i in items if i not in scored], key=lambda i: -i["evidence_count"])
        for it in (scored + weak)[:per_sector]:
            out.append({"sector_id": sid, "item": it})
    return out


def evidence_for(db, sector_id: str, topic: str, now: int, days: int = 90, limit: int = 6):
    rows = db.execute("SELECT source, title, link, published FROM items WHERE sector_id=? AND published>=? "
                      "AND (title LIKE ? OR summary LIKE ?) ORDER BY published DESC",
                      (sector_id, now - days * 86400, f"%{topic}%", f"%{topic}%")).fetchall()
    rows = rows[:limit]
    return [{"source": r[0], "title": r[1], "link": r[2], "published": r[3]} for r in rows]


def rule_vision(sector_id, item, sources, days=90):
    half = HALF[days]
    m = item["momentum"]
    facts = [f"{item['recent_count']} evidenze negli ultimi {half} giorni contro {item['previous_count']} nei {half} precedenti.",
             f"Fonti distinte che ne parlano: {item['independent_source_labels']}."]
    if m is not None:
        facts.append(f"Momentum calcolato: {m:+d} (scala da -100 a +100).")
    if m is not None and m > 0:
        hyp = ["Se il ritmo di crescita continua, l'argomento potrebbe consolidarsi nelle prossime settimane (ipotesi, non previsione)."]
        scen = [{"label": "Prosegue", "text": "Le evidenze continuano ad aumentare e l'argomento entra nel dibattito generale."},
                {"label": "Si ferma", "text": "Il picco era legato a pochi eventi e l'attenzione torna ai livelli precedenti."}]
        conf = "media"
    else:
        hyp = ["Segnale ancora debole: potrebbe essere rumore. Va solo tenuto d'occhio."]
        scen = [{"label": "Si conferma", "text": "Nei prossimi giorni compaiono nuove evidenze da fonti diverse."},
                {"label": "Svanisce", "text": "Non arrivano altre evidenze e il segnale scompare."}]
        conf = "bassa"
    return {"headline": f"{item['topic']}: " + ("in crescita" if conf == "media" else "segnale da osservare"),
            "facts": facts, "hypotheses": hyp, "scenarios": scen, "confidence": conf,
            "limits": "Basato su conteggi di notizie da poche fonti pubbliche: non misura qualita' o impatto reale.",
            "generated_by": "regole"}


PROMPT = """Sei l'analista di un'app di radar delle tendenze. Scrivi in italiano, tono sobrio.
USA SOLO i dati qui sotto. Non inventare numeri, aziende o eventi. Separa i FATTI (solo cose presenti nei dati)
dalle IPOTESI (interpretazioni, da dichiarare come tali). Nessuna previsione certa: solo scenari con limiti.
Dati: {data}
Rispondi SOLO con JSON: {{"headline": str (max 90 caratteri), "facts": [str] (2-4), "hypotheses": [str] (1-3),
"scenarios": [{{"label": str, "text": str}}] (2-3), "limits": str}}"""


def _valid(o) -> bool:
    return (isinstance(o, dict) and isinstance(o.get("headline"), str) and o["headline"].strip()
            and isinstance(o.get("facts"), list) and o["facts"] and all(isinstance(x, str) for x in o["facts"])
            and isinstance(o.get("hypotheses"), list) and all(isinstance(x, str) for x in o["hypotheses"])
            and isinstance(o.get("scenarios"), list)
            and all(isinstance(s, dict) and isinstance(s.get("label"), str) and isinstance(s.get("text"), str) for s in o["scenarios"])
            and isinstance(o.get("limits"), str))


def make_vision(sector_id, item, sources, gemini_call=None, days=90):
    base = rule_vision(sector_id, item, sources, days)
    if gemini_call:
        data = {"settore": SECTORS[sector_id]["name"], "argomento": item["topic"], "finestra_giorni": days,
                "evidenze_recenti": item["recent_count"], "evidenze_precedenti": item["previous_count"],
                "fonti_distinte": item["independent_source_labels"], "momentum": item["momentum"],
                "titoli_recenti": [s["title"] for s in sources]}
        try:
            txt = gemini_call(PROMPT.format(data=json.dumps(data, ensure_ascii=False)))
            o = json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip())
            if _valid(o):
                base.update({"headline": o["headline"][:120], "facts": o["facts"][:4],
                             "hypotheses": o["hypotheses"][:3], "scenarios": o["scenarios"][:3],
                             "limits": o["limits"], "generated_by": "gemini"})
        except Exception:
            pass  # resta la versione a regole
    base.update({"sector_id": sector_id, "sector_name": SECTORS[sector_id]["name"], "topic": item["topic"],
                 "sources": [{"title": s["title"], "link": s["link"], "source": s["source"]} for s in sources if s["link"]],
                 "baseline": {"momentum": item["momentum"], "recent": item["recent_count"],
                              "previous": item["previous_count"], "evidence_30": item.get("evidence_30", 0)}})
    return base


def make_gemini_call(key: str, model: str = None, timeout: int = 40):
    model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def call(prompt: str) -> str:
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                           "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4}}).encode()
        req = urllib.request.Request(url, body, {"Content-Type": "application/json", "x-goog-api-key": key})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.load(r)
        time.sleep(6.5)  # limite del piano gratuito: ~10 richieste al minuto
        return j["candidates"][0]["content"]["parts"][0]["text"]
    return call
