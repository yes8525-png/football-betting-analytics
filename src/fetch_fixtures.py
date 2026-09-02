"""Scarica il calendario partite dei prossimi giorni da football-data.org (richiede FOOTBALL_DATA_TOKEN)."""
import sys
import datetime
import requests
import pandas as pd

from config import FIXTURES_DIR, LEAGUES, FOOTBALL_DATA_TOKEN

API_URL = "https://api.football-data.org/v4/matches"


def fetch_fixtures(days_ahead: int = 2) -> pd.DataFrame:
    if not FOOTBALL_DATA_TOKEN:
        print("! FOOTBALL_DATA_TOKEN non impostato: salto il recupero fixture.", file=sys.stderr)
        return pd.DataFrame()

    today = datetime.date.today()
    date_from = today.isoformat()
    date_to = (today + datetime.timedelta(days=days_ahead)).isoformat()
    codes = ",".join(l["fd_org"] for l in LEAGUES)

    headers = {"X-Auth-Token": FOOTBALL_DATA_TOKEN}
    params = {"dateFrom": date_from, "dateTo": date_to, "competitions": codes}
    try:
        resp = requests.get(API_URL, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"! errore chiamando football-data.org: {e}", file=sys.stderr)
        return pd.DataFrame()

    rows = []
    for m in data.get("matches", []):
        rows.append({
            "match_id": m["id"],
            "competition": m["competition"]["name"],
            "competition_code": m["competition"]["code"],
            "utc_date": m["utcDate"],
            "status": m["status"],
            "home_team": m["homeTeam"]["name"],
            "away_team": m["awayTeam"]["name"],
            "home_score": (m.get("score", {}).get("fullTime", {}) or {}).get("home"),
            "away_score": (m.get("score", {}).get("fullTime", {}) or {}).get("away"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        out_path = FIXTURES_DIR / f"fixtures_{today.isoformat()}.csv"
        df.to_csv(out_path, index=False)
        # aggiorna anche un master file cumulativo (utile per il grading successivo)
        master_path = FIXTURES_DIR / "fixtures_master.csv"
        if master_path.exists():
            master = pd.read_csv(master_path)
            master = pd.concat([master, df], ignore_index=True).drop_duplicates(subset=["match_id"], keep="last")
        else:
            master = df
        master.to_csv(master_path, index=False)
        print(f"-> {len(df)} partite trovate nei prossimi {days_ahead} giorni, salvate in {out_path}")
    return df


if __name__ == "__main__":
    fetch_fixtures()
