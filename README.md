# ChronosLife-Radar

## Dati senza server (M3)
Una GitHub Action ("Daily data update", ogni giorno alle 04:17 UTC) raccoglie i feed gratuiti, calcola i trend e
pubblica i JSON sul ramo `data` (`trends/<settore>-<giorni>.json`, `items.jsonl`, `status.json`).
L'app li legge da raw.githubusercontent.com: nessun PC o server acceso, costo zero. Il repo deve essere pubblico.

    cd backend && python -m pytest -q          # test
    python -m app.publish /tmp/dati            # prova locale dell'aggiornamento

Settori, parole chiave e feed: `backend/app/sectors.py`. Momentum Score: (evidenze recenti - precedenti) / totale x 100
su due meta' della finestra; `null` sotto 5 evidenze o 2 fonti. Dal M3b i conteggi includono anche Hacker News (API gratuita con storico): per ogni parola non ambigua si contano
le storie nella meta' recente e in quella precedente, cosi' il Momentum esiste dal primo giorno (fonte aggiuntiva, `hackernews` in `status.json`).
L'archivio tiene solo le notizie che citano una
parola chiave (`items_scanned` conta quelle). Il server FastAPI (`app/main.py`) resta per uso locale/sviluppo.
