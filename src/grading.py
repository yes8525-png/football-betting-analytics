"""Confronta le previsioni registrate con i risultati reali, per calcolare calibrazione ed edge nel tempo.

Il risultato (1X2, over/under gol) arriva presto tramite football-data.org (status FINISHED).
Corner e cartellini arrivano piu' tardi, quando football-data.co.uk aggiorna il CSV della stagione
corrente: finche' non sono disponibili, quelle righe restano semplicemente non gradate (nessun dato
inventato).
"""
import pandas as pd
from config import PREDICTIONS_DIR, FIXTURES_DIR, RESULTS_DIR


def grade():
    pred_path = PREDICTIONS_DIR / "predictions_log.csv"
    fixtures_path = FIXTURES_DIR / "fixtures_master.csv"
    if not pred_path.exists() or not fixtures_path.exists():
        print("Niente da gradare ancora (mancano previsioni o fixture).")
        return

    preds = pd.read_csv(pred_path)
    fixtures = pd.read_csv(fixtures_path)
    finished = fixtures[fixtures["status"] == "FINISHED"][
        ["match_id", "home_score", "away_score"]
    ]

    merged = preds.merge(finished, on="match_id", how="inner")
    if merged.empty:
        print("Nessuna partita tra quelle previste risulta ancora conclusa.")
        return

    def outcome_correct(row):
        h, a = row["home_score"], row["away_score"]
        if pd.isna(h) or pd.isna(a):
            return None
        total = h + a
        if row["market"] == "1X2 - Home":
            return h > a
        if row["market"] == "1X2 - Draw":
            return h == a
        if row["market"] == "1X2 - Away":
            return a > h
        if row["market"] == "Over 2.5 goals":
            return total > 2.5
        if row["market"] == "Under 2.5 goals":
            return total < 2.5
        return None

    merged["correct"] = merged.apply(outcome_correct, axis=1)
    out_path = RESULTS_DIR / "results_grading.csv"
    merged.to_csv(out_path, index=False)

    graded = merged.dropna(subset=["correct"])
    if not graded.empty:
        accuracy = graded["correct"].mean()
        avg_edge = graded["estimated_edge"].mean()
        print(f"-> {len(graded)} previsioni gradate. Accuratezza grezza: {accuracy:.1%}. "
              f"Edge medio stimato: {avg_edge:.3f}" if avg_edge == avg_edge else "")
        print("Nota: campione ancora troppo piccolo per trarre conclusioni sull'affidabilita' del sistema.")


if __name__ == "__main__":
    grade()
