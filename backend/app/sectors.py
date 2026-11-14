"""Settori, parole chiave e fonti. Aggiungere un settore = aggiungere una voce qui (FR-10).
Gli id coincidono con quelli usati dall'app Android. Gli URL dei feed sono fonti pubbliche
gratuite: se uno cambia o smette di rispondere, l'ingestione lo salta e lo riporta."""

SECTORS = {
    "ai-tech": {
        "name": "AI e tecnologia",
        "feeds": [
            ("arxiv-cs-ai", "https://rss.arxiv.org/rss/cs.AI"),
            ("arxiv-cs-ro", "https://rss.arxiv.org/rss/cs.RO"),
            ("huggingface-blog", "https://huggingface.co/blog/feed.xml"),
        ],
        "keywords": ["AI agent", "agentic", "multimodal", "reasoning", "robotics",
                     "humanoid", "open-source model", "fine-tuning", "RAG", "automation"],
    },
    "operations": {
        "name": "Industria e Operations",
        "feeds": [
            ("supplychaindive", "https://www.supplychaindive.com/feeds/news/"),
            ("manufacturingdive", "https://www.manufacturingdive.com/feeds/news/"),
        ],
        "keywords": ["supply chain", "logistics", "ERP", "SAP", "automation", "warehouse",
                     "tariff", "reshoring", "digital twin", "predictive maintenance"],
    },
    "sport": {
        "name": "Sport e innovazione",
        "feeds": [
            ("dcrainmaker", "https://www.dcrainmaker.com/feed"),
            ("sciencedaily-sports", "https://www.sciencedaily.com/rss/health_medicine/sports_medicine.xml"),
        ],
        "keywords": ["wearable", "smartwatch", "carbon plate", "biomechanics", "heart rate",
                     "running shoe", "training load", "recovery", "sensor", "GPS"],
    },
}

# Parole troppo ambigue per la ricerca a testo libero su Hacker News (darebbero conteggi falsati).
HN_SKIP = {"RAG", "SAP", "ERP", "GPS", "sensor", "recovery", "reasoning", "automation", "tariff"}
