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

## Visioni giornaliere (M4)
L'Action giornaliera genera `visions/<data>.json` (+ `latest.json`, `index.json`), `links.json` e `verification.json` sul ramo `data`.
- Testo scritto da **Gemini (gratuito)** se esiste il segreto `GEMINI_API_KEY`; altrimenti da regole fisse (indicato nell'app).
- Ogni visione separa **fatti** (dai dati) da **ipotesi**, ha scenari e limiti dichiarati; le fonti allegate vengono dai nostri dati, mai dal modello.
- Verifica: dopo 30/90 giorni si ricontrolla se un argomento "in crescita" e' cresciuto di almeno il 15%.
- App: tab Visioni, Radar, Watchlist (con note), Collegamenti, Archivio (con verifica).
Chiave gratuita: https://aistudio.google.com/apikey -> Settings > Secrets and variables > Actions > New repository secret `GEMINI_API_KEY`.

## Sezioni personalizzate, icona e APK (M5)
- Tab **Sezioni**: aggiungi un settore con un titolo (e argomenti facoltativi); l'app lo analizza subito dal telefono con fonti
  gratuite (Hacker News per il Momentum, Google News per i titoli), senza server. Salvate sul telefono; gli argomenti si possono mettere in Watchlist.
- Icona adaptive Material: radar giallo su sfondo blu con "Cronos" (generata da script, vedi `android/app/src/main/res/mipmap-*`).
- APK: artefatto **CronosLife-Radar** (file `CronosLife-Radar.apk`). Firmato con una chiave di debug fissa (`android/app/debug.keystore`,
  password di debug pubblica): cosi' ogni nuova versione si installa sopra la precedente senza disinstallare.
