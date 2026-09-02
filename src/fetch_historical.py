"""Scarica gli storici da football-data.co.uk (nessuna chiave richiesta).

Formato stabile dal 2000/01: risultati, calci d'angolo (HC/AC), cartellini (HY/AY/HR/AR), quote storiche.
Non e' una API "fragile": sono file CSV distribuiti direttamente dal sito, con schema di colonne
invariato da oltre 20 anni.
"""
import sys
import requests
import pandas as pd

from config import HISTORICAL_DIR, LEAGUES, current_season_code

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"

# Quante stagioni indietro scaricare per il backtesting (oltre alla corrente).
SEASONS_BACK = 8


def season_codes(n_back=SEASONS_BACK):
    import datetime
    today = datetime.date.today()
    start_year = today.year if today.month >= 7 else today.year - 1
    codes = []
    for i in range(n_back + 1):
        y0 = start_year - i
        y1 = y0 + 1
        codes.append(f"{str(y0)[2:]}{str(y1)[2:]}")
    return codes


def fetch_one(code: str, season: str) -> pd.DataFrame | None:
    url = BASE_URL.format(season=season, code=code)
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200 or len(resp.content) < 100:
            return None
        from io import StringIO
        df = pd.read_csv(StringIO(resp.content.decode("latin-1")), on_bad_lines="skip")
        df["Season"] = season
        df["LeagueCode"] = code
        return df
    except Exception as e:
        print(f"  ! errore scaricando {code} {season}: {e}", file=sys.stderr)
        return None


def fetch_all():
    for league in LEAGUES:
        code = league["fd_couk"]
        if code is None:
            continue  # es. Champions League, non coperta da football-data.co.uk
        frames = []
        for season in season_codes():
            df = fetch_one(code, season)
            if df is not None:
                frames.append(df)
                print(f"  ok {league['name']} {season}: {len(df)} partite")
        if frames:
            out = pd.concat(frames, ignore_index=True)
            out_path = HISTORICAL_DIR / f"{code}.csv"
            out.to_csv(out_path, index=False)
            print(f"-> salvato {out_path} ({len(out)} righe totali)")


if __name__ == "__main__":
    fetch_all()
