"""Scarica le quote multi-bookmaker da The Odds API (richiede ODDS_API_KEY).

Piano free = 500 crediti/mese: usare con parsimonia (uno snapshot al giorno, non polling continuo).
"""
import sys
import datetime
import requests
import pandas as pd

from config import ODDS_DIR, LEAGUES, ODDS_API_KEY

BASE_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"


def fetch_odds_for_league(sport_key: str, league_name: str) -> pd.DataFrame:
    if not ODDS_API_KEY:
        print("! ODDS_API_KEY non impostato: salto il recupero quote.", file=sys.stderr)
        return pd.DataFrame()

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu,uk",
        "markets": "h2h,totals",
        "oddsFormat": "decimal",
    }
    try:
        resp = requests.get(BASE_URL.format(sport=sport_key), params=params, timeout=20)
        remaining = resp.headers.get("x-requests-remaining")
        if remaining is not None:
            print(f"  crediti The Odds API rimanenti questo mese: {remaining}")
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        print(f"! errore chiamando The Odds API per {league_name}: {e}", file=sys.stderr)
        return pd.DataFrame()

    rows = []
    now = datetime.datetime.utcnow().isoformat()
    for ev in events:
        for bk in ev.get("bookmakers", []):
            for market in bk.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "snapshot_utc": now,
                        "league": league_name,
                        "commence_time": ev.get("commence_time"),
                        "home_team": ev.get("home_team"),
                        "away_team": ev.get("away_team"),
                        "bookmaker": bk.get("key"),
                        "market": market.get("key"),
                        "selection": outcome.get("name"),
                        "point": outcome.get("point"),
                        "odds": outcome.get("price"),
                    })
    return pd.DataFrame(rows)


def fetch_all() -> pd.DataFrame:
    frames = []
    for league in LEAGUES:
        df = fetch_odds_for_league(league["odds_api"], league["name"])
        if not df.empty:
            frames.append(df)
            print(f"  ok {league['name']}: {len(df)} righe quote")
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    today = datetime.date.today().isoformat()
    out_path = ODDS_DIR / f"odds_{today}.csv"
    out.to_csv(out_path, index=False)

    master_path = ODDS_DIR / "odds_snapshots.csv"
    if master_path.exists():
        master = pd.read_csv(master_path)
        master = pd.concat([master, out], ignore_index=True)
    else:
        master = out
    master.to_csv(master_path, index=False)
    print(f"-> salvato snapshot quote in {out_path} ({len(out)} righe)")
    return out


if __name__ == "__main__":
    fetch_all()
