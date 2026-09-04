"""Genera un riepilogo leggibile (Markdown) delle previsioni per le partite in programma,
piu' un breve richiamo di come sta andando il modello sulle previsioni gia' concluse.

Pensato per essere aperto comodamente su GitHub (che rende il markdown in una pagina leggibile
con tabelle), invece di dover aprire il CSV grezzo ogni volta.
"""
import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from config import PREDICTIONS_DIR, RESULTS_DIR

ROME = ZoneInfo("Europe/Rome")

MARKET_LABELS = {
    "1X2 - Home": "1 (vittoria casa)",
    "1X2 - Draw": "X (pareggio)",
    "1X2 - Away": "2 (vittoria trasferta)",
    "Over 2.5 goals": "Over 2.5 gol",
    "Under 2.5 goals": "Under 2.5 gol",
}


def _fmt_pct(x):
    return f"{x*100:.1f}%" if pd.notna(x) else "-"


def _fmt_odds(x):
    return f"{x:.2f}" if pd.notna(x) else "-"


def _fmt_edge(x):
    if pd.isna(x):
        return "-"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x*100:.1f}%"


def _to_rome(utc_iso):
    try:
        dt = pd.to_datetime(utc_iso, utc=True)
        return dt.tz_convert(ROME)
    except Exception:
        return None


def build_report():
    pred_path = PREDICTIONS_DIR / "predictions_log.csv"
    if not pred_path.exists():
        print("Nessuna previsione ancora registrata: report non generato.")
        return

    preds = pd.read_csv(pred_path)
    if preds.empty:
        print("predictions_log.csv vuoto: report non generato.")
        return

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    preds["kickoff_dt"] = pd.to_datetime(preds["kickoff_utc"], utc=True, errors="coerce")
    upcoming = preds[preds["kickoff_dt"] >= now_utc].copy()
    # Tiene solo l'ultima previsione generata per ogni combinazione match/mercato,
    # nel caso la pipeline sia girata piu' volte sulla stessa partita.
    upcoming = upcoming.sort_values("generated_utc").drop_duplicates(
        subset=["match_id", "market"], keep="last"
    )

    lines = []
    lines.append("# Previsioni in programma")
    lines.append("")
    lines.append(f"Generato il {datetime.datetime.now(ROME).strftime('%d/%m/%Y alle %H:%M')} (ora italiana).")
    lines.append("")
    lines.append(
        "Nota: sistema in fase di test/carta, nessuna scommessa reale. Le probabilita' sono "
        "stime di un modello statistico (Poisson) basato sullo storico delle squadre, non certezze."
    )
    lines.append("")

    # --- Breve richiamo performance storica, se disponibile ---
    grading_path = RESULTS_DIR / "results_grading.csv"
    if grading_path.exists():
        graded = pd.read_csv(grading_path)
        graded = graded.dropna(subset=["correct"]) if "correct" in graded.columns else pd.DataFrame()
        if not graded.empty:
            accuracy = graded["correct"].mean()
            avg_edge = graded["estimated_edge"].mean()
            lines.append(
                f"**Finora:** {len(graded)} previsioni gia' concluse e verificate. "
                f"Accuratezza grezza: {accuracy*100:.1f}%. Edge medio stimato: "
                f"{avg_edge*100:.1f}%. Campione ancora piccolo, non e' un segnale affidabile."
            )
            lines.append("")

    if upcoming.empty:
        lines.append("Nessuna partita in programma nelle prossime ore con previsioni disponibili.")
        content = "\n".join(lines)
        out_path = PREDICTIONS_DIR / "report_oggi.md"
        out_path.write_text(content, encoding="utf-8")
        print(f"-> report generato (nessuna partita in programma) in {out_path}")
        return

    # --- Una sezione per ogni partita, in ordine di calcio d'inizio ---
    match_order = upcoming.groupby("match_id")["kickoff_dt"].min().sort_values().index

    for match_id in match_order:
        rows = upcoming[upcoming["match_id"] == match_id]
        first = rows.iloc[0]
        kickoff_rome = _to_rome(first["kickoff_utc"])
        kickoff_str = kickoff_rome.strftime("%a %d/%m %H:%M") if kickoff_rome is not None else "-"
        lines.append(f"## {first['home_team']} - {first['away_team']}")
        lines.append(f"*{first['competition']} — {kickoff_str}*")
        lines.append("")
        lines.append("| Mercato | Probabilita' modello | Quota mercato | Prob. implicita quota | Edge stimato |")
        lines.append("|---|---|---|---|---|")
        for _, r in rows.iterrows():
            label = MARKET_LABELS.get(r["market"], r["market"])
            lines.append(
                f"| {label} | {_fmt_pct(r['model_probability'])} | {_fmt_odds(r['market_odds'])} "
                f"| {_fmt_pct(r['market_implied_probability'])} | {_fmt_edge(r['estimated_edge'])} |"
            )
        extra = []
        if pd.notna(first.get("home_xg")) and pd.notna(first.get("away_xg")):
            extra.append(f"Gol attesi: {first['home_xg']:.2f} - {first['away_xg']:.2f}")
        if pd.notna(first.get("expected_corners")):
            extra.append(f"Corner attesi (totale): {first['expected_corners']:.1f}")
        if pd.notna(first.get("expected_cards")):
            extra.append(f"Cartellini attesi (totale): {first['expected_cards']:.1f}")
        if extra:
            lines.append("")
            lines.append(" · ".join(extra))
        lines.append("")

    content = "\n".join(lines)
    out_path = PREDICTIONS_DIR / "report_oggi.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"-> report leggibile generato in {out_path} ({len(match_order)} partite)")


if __name__ == "__main__":
    build_report()
