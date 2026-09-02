"""Calcola le statistiche "di forma" delle squadre a partire dagli storici football-data.co.uk."""
import pandas as pd
from config import HISTORICAL_DIR


def load_league_history(fd_couk_code: str) -> pd.DataFrame:
    path = HISTORICAL_DIR / f"{fd_couk_code}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    return df.dropna(subset=["Date", "HomeTeam", "AwayTeam"])


def league_averages(df: pd.DataFrame) -> dict:
    """Medie di lega: gol/corner/cartellini casa e trasferta. Base per il modello di Poisson."""
    if df.empty:
        return {}
    return {
        "avg_home_goals": df["FTHG"].mean(),
        "avg_away_goals": df["FTAG"].mean(),
        "avg_home_corners": df["HC"].mean() if "HC" in df else None,
        "avg_away_corners": df["AC"].mean() if "AC" in df else None,
        "avg_home_cards": (df.get("HY", 0).fillna(0) + df.get("HR", 0).fillna(0) * 2).mean() if "HY" in df else None,
        "avg_away_cards": (df.get("AY", 0).fillna(0) + df.get("AR", 0).fillna(0) * 2).mean() if "AY" in df else None,
    }


def team_form(df: pd.DataFrame, team: str, as_of=None, n_matches: int = 15) -> dict:
    """Statistiche recenti di una squadra (ultime n_matches, casa+trasferta), usate per stimare
    forza d'attacco/difesa nel modello. Ritorna None se non ci sono abbastanza dati.
    """
    if df.empty:
        return None
    sub = df[(df["HomeTeam"] == team) | (df["AwayTeam"] == team)].sort_values("Date")
    if as_of is not None:
        sub = sub[sub["Date"] < as_of]
    sub = sub.tail(n_matches)
    if sub.empty:
        return None

    scored, conceded, corners_for, corners_against, cards_for = [], [], [], [], []
    for _, row in sub.iterrows():
        is_home = row["HomeTeam"] == team
        scored.append(row["FTHG"] if is_home else row["FTAG"])
        conceded.append(row["FTAG"] if is_home else row["FTHG"])
        if "HC" in row and pd.notna(row.get("HC")):
            corners_for.append(row["HC"] if is_home else row["AC"])
            corners_against.append(row["AC"] if is_home else row["HC"])
        if "HY" in row and pd.notna(row.get("HY")):
            y = row["HY"] if is_home else row["AY"]
            r = row.get("HR", 0) if is_home else row.get("AR", 0)
            cards_for.append((y or 0) + (r or 0) * 2)

    def avg(lst):
        return sum(lst) / len(lst) if lst else None

    return {
        "matches": len(sub),
        "goals_for": avg(scored),
        "goals_against": avg(conceded),
        "corners_for": avg(corners_for),
        "corners_against": avg(corners_against),
        "cards_for": avg(cards_for),
    }
