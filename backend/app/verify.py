"""Verifica delle anticipazioni: dopo 30/90 giorni confronta le evidenze degli ultimi 30 giorni con quelle
registrate al momento della visione. 'Confermata' = crescita di almeno il 15%."""
HORIZONS = (30, 90)
GROWTH = 1.15


def outcome(base: int, now: int) -> str:
    if base == 0:
        return "up" if now >= 3 else "flat"
    if now >= base * GROWTH:
        return "up"
    if now <= base / GROWTH:
        return "down"
    return "flat"


def update(existing: dict, visions_by_date: dict, trends30: dict, today: str, now: int):
    """visions_by_date: {'2026-11-15': [vision,...]}; trends30: {sector: compute_trends(.., 30)}."""
    from datetime import date
    items = list(existing.get("items", []))
    done = {(i["date"], i["sector_id"], i["topic"], i["horizon_days"]) for i in items}
    d_today = date.fromisoformat(today)
    for d, visions in visions_by_date.items():
        age = (d_today - date.fromisoformat(d)).days
        for v in visions:
            b = v.get("baseline") or {}
            if not b.get("momentum") or b["momentum"] <= 0:
                continue  # verifichiamo solo le anticipazioni "in crescita"
            for h in HORIZONS:
                key = (d, v["sector_id"], v["topic"], h)
                if age < h or key in done:
                    continue
                cur = {i["topic"]: i["evidence_count"] for i in trends30.get(v["sector_id"], {}).get("items", [])}
                nowc = cur.get(v["topic"], 0)
                res = outcome(b.get("evidence_30", 0), nowc)
                items.append({"date": d, "sector_id": v["sector_id"], "topic": v["topic"], "horizon_days": h,
                              "predicted": "up", "outcome": res, "hit": res == "up",
                              "base_30": b.get("evidence_30", 0), "now_30": nowc})
    return {"updated": now, "checked": len(items), "confirmed": sum(1 for i in items if i["hit"]), "items": items[-200:]}
