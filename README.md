# Football Betting Analytics

Sistema che raccoglie ogni giorno dati sulle partite di calcio (Top 5 campionati europei + Champions League),
li analizza (statistiche storiche, quote multi-bookmaker, volumi Betfair) e registra previsioni **prima**
del calcio d'inizio, per poterle confrontare con i risultati reali **dopo** la partita.

**Fase attuale: solo test/carta. Zero soldi reali scommessi finché il sistema non è validato.**
Vedi la sezione "Criteri per passare a soldi veri" più sotto.

## Perché esiste

Non un modello che "indovina il 90%" (non esiste nel calcio: le quote dei bookmaker sono fatte apposta
per pareggiare i flussi e tenersi un margine). L'obiettivo è trovare sistematicamente un vantaggio
misurabile rispetto al mercato (edge / valore atteso positivo), verificato su un campione ampio prima
di rischiare qualsiasi somma reale.

## Stato del progetto

| Componente | Stato |
|---|---|
| Dati storici (corner, cartellini, risultati, quote storiche) — football-data.co.uk | ✅ Funzionante, nessuna chiave richiesta |
| Fixture / calendario partite — football-data.org | ⏳ Richiede `FOOTBALL_DATA_TOKEN` |
| Quote multi-bookmaker — The Odds API | ⏳ Richiede `ODDS_API_KEY` |
| Volumi / flusso soldi — Betfair Exchange | ⏳ Fase 2 (autenticazione più complessa, vedi sotto) |
| Modello di previsione (Poisson) | ✅ Baseline funzionante |
| Modulo di grading (previsione vs realtà) | ✅ Baseline funzionante |
| Automazione giornaliera (GitHub Actions) | ✅ Configurata, parte automaticamente ogni giorno una volta aggiunti i secrets |

## Come aggiungere le chiavi API (secrets)

Le chiavi **non vanno mai messe nel codice o in chat**: si aggiungono direttamente su GitHub, dove
solo l'automazione può leggerle.

1. Vai sul repository → **Settings** → **Secrets and variables** → **Actions**.
2. Clicca **New repository secret** e aggiungi, uno alla volta:
   - `FOOTBALL_DATA_TOKEN` — il token che ottieni registrandoti gratis su [football-data.org](https://www.football-data.org)
   - `ODDS_API_KEY` — la chiave che ottieni registrandoti gratis su [the-odds-api.com](https://the-odds-api.com)
3. Fatto questo, il workflow giornaliero (`.github/workflows/daily.yml`) può girare completo.

Per Betfair (Fase 2): l'autenticazione richiede username, password e Application Key insieme — dati più
sensibili di una semplice API key, quindi **non vanno mai scritti in chat con Claude**: si aggiungono
allo stesso modo come repository secrets (`BETFAIR_APP_KEY`, `BETFAIR_USERNAME`, `BETFAIR_PASSWORD`)
quando questa fase verrà attivata.

## Come si esegue manualmente

Il workflow gira automaticamente ogni giorno, ma puoi anche lanciarlo a mano da GitHub:
**Actions** → **Daily pipeline** → **Run workflow**.

In locale (per sviluppo):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/daily_pipeline.py
```

## Struttura dati

- `data/historical/` — CSV storici dal 2000/01 a oggi (football-data.co.uk): risultati, corner, cartellini, quote
- `data/fixtures/` — calendario partite del giorno (football-data.org)
- `data/odds/` — snapshot quote multi-bookmaker (The Odds API)
- `data/betfair/` — volumi scambiati (Fase 2)
- `data/predictions/predictions_log.csv` — ogni previsione generata PRIMA del match, con probabilità stimata,
  quota di mercato, edge stimato, timestamp
- `data/results/results_grading.csv` — confronto previsione vs realtà, per calcolare calibrazione ed edge nel tempo

## Criteri per passare a soldi veri (non ancora raggiunti)

- Almeno alcune centinaia di previsioni "graded" per ciascun mercato che si vuole giocare
- Calibrazione buona: quando il modello dice "60% di probabilità", quell'evento si verifica ~60% delle volte
- Closing Line Value (CLV) positivo in modo consistente
- ROI simulato (su carta) positivo su un campione ampio, tenendo conto della varianza naturale del calcio

## Nota tecnica

Le chiamate alle API esterne (football-data.org, The Odds API, Betfair) girano sui runner di GitHub Actions,
non dall'ambiente di sviluppo di Claude, che ha accesso di rete limitato per policy di sicurezza. Questo
è anche il motivo per cui l'automazione è basata su GitHub Actions e non su una sessione Claude sempre aperta:
è pensata per funzionare in modo indipendente, tutti i giorni, senza bisogno che nessuno dei due sia online.
