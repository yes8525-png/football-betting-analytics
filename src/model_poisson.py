"""Modello baseline: Poisson su gol attesi (stile Dixon-Coles semplificato), piu' una stima
analoga per corner e cartellini basata sulle medie di forma. E' un punto di partenza, non un
modello raffinato: serve per iniziare a registrare previsioni e costruire lo storico di grading.
"""
from scipy.stats import poisson
import numpy as np


def expected_goals(home_form, away_form, league_avg):
    """Forza attacco/difesa relative alla media di lega, poi combinate per stimare i gol attesi."""
    home_attack = (home_form["goals_for"] or league_avg["avg_home_goals"]) / league_avg["avg_home_goals"]
    home_defense = (home_form["goals_against"] or league_avg["avg_away_goals"]) / league_avg["avg_away_goals"]
    away_attack = (away_form["goals_for"] or league_avg["avg_away_goals"]) / league_avg["avg_away_goals"]
    away_defense = (away_form["goals_against"] or league_avg["avg_home_goals"]) / league_avg["avg_home_goals"]

    home_xg = league_avg["avg_home_goals"] * home_attack * away_defense
    away_xg = league_avg["avg_away_goals"] * away_attack * home_defense
    return max(home_xg, 0.05), max(away_xg, 0.05)


def match_probabilities(home_xg: float, away_xg: float, max_goals: int = 8) -> dict:
    home_probs = [poisson.pmf(i, home_xg) for i in range(max_goals + 1)]
    away_probs = [poisson.pmf(i, away_xg) for i in range(max_goals + 1)]
    matrix = np.outer(home_probs, away_probs)

    p_home = np.tril(matrix, -1).sum()
    p_draw = np.trace(matrix)
    p_away = np.triu(matrix, 1).sum()

    over_25 = sum(matrix[i, j] for i in range(max_goals + 1) for j in range(max_goals + 1) if i + j > 2)
    under_25 = 1 - over_25

    # top 3 risultati esatti piu' probabili
    scores = [((i, j), matrix[i, j]) for i in range(max_goals + 1) for j in range(max_goals + 1)]
    scores.sort(key=lambda x: -x[1])
    top_scores = scores[:3]

    return {
        "home_xg": round(home_xg, 2),
        "away_xg": round(away_xg, 2),
        "p_home": round(p_home, 4),
        "p_draw": round(p_draw, 4),
        "p_away": round(p_away, 4),
        "p_over_2_5": round(over_25, 4),
        "p_under_2_5": round(under_25, 4),
        "top_correct_scores": [(f"{s[0][0]}-{s[0][1]}", round(s[1], 4)) for s in top_scores],
    }


def expected_corners(home_form, away_form, league_avg, line: float = 9.5) -> dict:
    if not (home_form.get("corners_for") and away_form.get("corners_for") and league_avg.get("avg_home_corners")):
        return {}
    home_exp = (home_form["corners_for"] + away_form.get("corners_against", home_form["corners_for"])) / 2
    away_exp = (away_form["corners_for"] + home_form.get("corners_against", away_form["corners_for"])) / 2
    total_exp = home_exp + away_exp
    # approssimazione Poisson sul totale
    over = 1 - poisson.cdf(int(line), total_exp)
    return {"expected_total_corners": round(total_exp, 2), "line": line,
            "p_over": round(over, 4), "p_under": round(1 - over, 4)}


def expected_cards(home_form, away_form, line: float = 3.5) -> dict:
    if not (home_form.get("cards_for") and away_form.get("cards_for")):
        return {}
    total_exp = home_form["cards_for"] + away_form["cards_for"]
    over = 1 - poisson.cdf(int(line), total_exp)
    return {"expected_total_cards": round(total_exp, 2), "line": line,
            "p_over": round(over, 4), "p_under": round(1 - over, 4)}


def implied_probability(decimal_odds: float) -> float:
    if not decimal_odds or decimal_odds <= 1:
        return None
    return 1 / decimal_odds
