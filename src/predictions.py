"""Genera e registra le previsioni PRIMA del calcio d'inizio (predictions_log.csv)."""
import uuid
import datetime
import pandas as pd

from config import PREDICTIONS_DIR, LEAGUES
import team_stats
import model_poisson
import name_matching


def build_predictions(fixtures: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    if fixtures.empty:
        print("Nessuna fixture disponibile: niente previsioni da generare.")
        return pd.DataFrame()

    league_by_code = {l["fd_org"]: l for l in LEAGUES}
    now = datetime.datetime.utcnow().isoformat()
    rows = []

    for _, fx in fixtures.iterrows():
        label = f"{fx['home_team']} - {fx['away_team']} ({fx['competition']})"
        league = league_by_code.get(fx["competition_code"])
        if league is None or league["fd_couk"] is None:
            print(f"  salto {label}: competizione senza storico disponibile (es. Champions League)")
            continue

        hist = team_stats.load_league_history(league["fd_couk"])
        if hist.empty:
            print(f"  salto {label}: nessuno storico trovato per {league['fd_couk']}")
            continue
        league_avg = team_stats.league_averages(hist)

        candidates = sorted(set(hist["HomeTeam"].dropna()) | set(hist["AwayTeam"].dropna()))
        home_match = name_matching.best_match(fx["home_team"], candidates)
        away_match = name_matching.best_match(fx["away_team"], candidates)

        if not home_match or not away_match:
            print(f"  salto {label}: nome squadra non riconosciuto nello storico "
                  f"(casa: {fx['home_team']!r} -> {home_match!r}, "
                  f"trasferta: {fx['away_team']!r} -> {away_match!r})")
            continue
        if home_match == away_match:
            print(f"  salto {label}: match ambiguo, casa e trasferta risolte sulla stessa squadra ({home_match!r})")
            continue

        home_form = team_stats.team_form(hist, home_match)
        away_form = team_stats.team_form(hist, away_match)
        if not home_form or not away_form:
            print(f"  salto {label}: dati di forma insufficienti per {home_match}/{away_match}")
            continue

        home_xg, away_xg = model_poisson.expected_goals(home_form, away_form, league_avg)
        probs = model_poisson.match_probabilities(home_xg, away_xg)
        corners = model_poisson.expected_corners(home_form, away_form, league_avg)
        cards = model_poisson.expected_cards(home_form, away_form)

        match_odds = odds[(odds["home_team"] == fx["home_team"]) & (odds["away_team"] == fx["away_team"])] \
            if not odds.empty else pd.DataFrame()

        def best_odds(market, selection):
            if match_odds.empty:
                return None
            sub = match_odds[(match_odds["market"] == market) & (match_odds["selection"] == selection)]
            return sub["odds"].max() if not sub.empty else None

        market_defs = [
            ("1X2 - Home", probs["p_home"], best_odds("h2h", fx["home_team"])),
            ("1X2 - Draw", probs["p_draw"], best_odds("h2h", "Draw")),
            ("1X2 - Away", probs["p_away"], best_odds("h2h", fx["away_team"])),
            ("Over 2.5 goals", probs["p_over_2_5"], best_odds("totals", "Over")),
            ("Under 2.5 goals", probs["p_under_2_5"], best_odds("totals", "Under")),
        ]

        for market_name, model_prob, market_odds_val in market_defs:
            implied = model_poisson.implied_probability(market_odds_val) if market_odds_val else None
            edge = (model_prob - implied) if implied is not None else None
            rows.append({
                "prediction_id": str(uuid.uuid4())[:8],
                "generated_utc": now,
                "match_id": fx["match_id"],
                "competition": fx["competition"],
                "home_team": fx["home_team"],
                "away_team": fx["away_team"],
                "kickoff_utc": fx["utc_date"],
                "market": market_name,
                "model_probability": model_prob,
                "market_odds": market_odds_val,
                "market_implied_probability": round(implied, 4) if implied else None,
                "estimated_edge": round(edge, 4) if edge is not None else None,
                "home_xg": probs["home_xg"],
                "away_xg": probs["away_xg"],
                "expected_corners": corners.get("expected_total_corners"),
                "expected_cards": cards.get("expected_total_cards"),
                "model_version": "poisson_baseline_v0",
            })
        print(f"  ok {label}: previsioni generate ({home_match} / {away_match})")

    return pd.DataFrame(rows)


def save_predictions(df: pd.DataFrame):
    if df.empty:
        print("Nessuna previsione generata (vedi sopra i motivi per ogni partita saltata).")
        return
    master_path = PREDICTIONS_DIR / "predictions_log.csv"
    if master_path.exists():
        master = pd.read_csv(master_path)
        master = pd.concat([master, df], ignore_index=True)
    else:
        master = df
    master.to_csv(master_path, index=False)
    print(f"-> {len(df)} nuove previsioni registrate in {master_path}")
