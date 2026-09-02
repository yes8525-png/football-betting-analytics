"""Configurazione centrale: leghe coperte, mapping tra le diverse fonti dati, chiavi da env."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
HISTORICAL_DIR = DATA_DIR / "historical"
FIXTURES_DIR = DATA_DIR / "fixtures"
ODDS_DIR = DATA_DIR / "odds"
BETFAIR_DIR = DATA_DIR / "betfair"
PREDICTIONS_DIR = DATA_DIR / "predictions"
RESULTS_DIR = DATA_DIR / "results"

for d in (HISTORICAL_DIR, FIXTURES_DIR, ODDS_DIR, BETFAIR_DIR, PREDICTIONS_DIR, RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Chiavi API: lette da variabili d'ambiente (settate come GitHub Actions secrets in produzione).
FOOTBALL_DATA_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
BETFAIR_APP_KEY = os.environ.get("BETFAIR_APP_KEY")
BETFAIR_USERNAME = os.environ.get("BETFAIR_USERNAME")
BETFAIR_PASSWORD = os.environ.get("BETFAIR_PASSWORD")

# Le 5 leghe top + Champions League, con il mapping fra le tre fonti dati.
# fd_org: codice competizione su football-data.org (fixture/calendario)
# fd_couk: codice su football-data.co.uk (storico risultati/corner/cartellini), None se non coperta
# odds_api_key: "sport key" su The Odds API (quote multi-bookmaker)
LEAGUES = [
    {"name": "Premier League", "fd_org": "PL", "fd_couk": "E0", "odds_api": "soccer_epl"},
    {"name": "Serie A", "fd_org": "SA", "fd_couk": "I1", "odds_api": "soccer_italy_serie_a"},
    {"name": "La Liga", "fd_org": "PD", "fd_couk": "SP1", "odds_api": "soccer_spain_la_liga"},
    {"name": "Bundesliga", "fd_org": "BL1", "fd_couk": "D1", "odds_api": "soccer_germany_bundesliga"},
    {"name": "Ligue 1", "fd_org": "FL1", "fd_couk": "F1", "odds_api": "soccer_france_ligue_one"},
    {"name": "Champions League", "fd_org": "CL", "fd_couk": None, "odds_api": "soccer_uefa_champs_league"},
]

# Le sport key di The Odds API vanno verificate periodicamente contro l'endpoint /v4/sports
# (possono cambiare leggermente). Se una lega smette di restituire dati, controllare lì per primo.

# Stagione corrente in formato football-data.co.uk (es. 2026/27 -> "2627")
def current_season_code(today=None):
    import datetime
    today = today or datetime.date.today()
    # la stagione europea parte a luglio/agosto: se siamo tra luglio e dicembre e' anno-anno+1,
    # se siamo tra gennaio e giugno e' anno-1-anno
    if today.month >= 7:
        start, end = today.year, today.year + 1
    else:
        start, end = today.year - 1, today.year
    return f"{str(start)[2:]}{str(end)[2:]}"
