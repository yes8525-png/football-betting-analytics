"""Orchestratore: gira una volta al giorno (via GitHub Actions).

1. Aggiorna gli storici (football-data.co.uk) - leggero, si puo' fare ogni giorno.
2. Scarica le fixture dei prossimi 2 giorni (football-data.org).
3. Scarica uno snapshot di quote (The Odds API) - con parsimonia, piano free limitato.
4. (Fase 2) Volumi Betfair.
5. Genera previsioni con il modello baseline e le registra PRIMA del calcio d'inizio.
6. Gradua le previsioni delle partite gia' concluse.
7. Genera un riepilogo leggibile in Markdown delle previsioni in programma.

Ogni step e' avvolto in try/except: se una fonte fallisce (chiave mancante, rate limit, sito giu'),
il resto della pipeline continua comunque.
"""
import sys
import pandas as pd

import fetch_historical
import fetch_fixtures
import fetch_odds
import fetch_betfair
import predictions
import grading
import report


def run():
    print("== 1. Storici (football-data.co.uk) ==")
    try:
        fetch_historical.fetch_all()
    except Exception as e:
        print(f"! step storici fallito: {e}", file=sys.stderr)

    print("== 2. Fixture (football-data.org) ==")
    try:
        fixtures = fetch_fixtures.fetch_fixtures()
    except Exception as e:
        print(f"! step fixture fallito: {e}", file=sys.stderr)
        fixtures = pd.DataFrame()

    print("== 3. Quote (The Odds API) ==")
    try:
        odds = fetch_odds.fetch_all()
    except Exception as e:
        print(f"! step quote fallito: {e}", file=sys.stderr)
        odds = pd.DataFrame()

    print("== 4. Volumi Betfair (Fase 2) ==")
    try:
        fetch_betfair.fetch_all()
    except NotImplementedError:
        pass
    except Exception as e:
        print(f"! step Betfair fallito: {e}", file=sys.stderr)

    print("== 5. Previsioni ==")
    try:
        preds = predictions.build_predictions(fixtures, odds)
        predictions.save_predictions(preds)
    except Exception as e:
        print(f"! step previsioni fallito: {e}", file=sys.stderr)

    print("== 6. Grading previsioni passate ==")
    try:
        grading.grade()
    except Exception as e:
        print(f"! step grading fallito: {e}", file=sys.stderr)

    print("== 7. Report leggibile (data/predictions/report_oggi.md) ==")
    try:
        report.build_report()
    except Exception as e:
        print(f"! step report fallito: {e}", file=sys.stderr)

    print("== Fine pipeline giornaliera ==")


if __name__ == "__main__":
    run()
