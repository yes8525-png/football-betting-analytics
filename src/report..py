"""Genera un riepilogo leggibile delle previsioni per le partite in programma, sia in Markdown
(per essere aperto comodamente su GitHub) sia in HTML (per essere scaricato e aperto nel browser
come una vera pagina web), piu' un breve richiamo di come sta andando il modello sulle previsioni
gia' concluse.
"""
import datetime
from zoneinfo import ZoneInfo
import pandas as pd

from config import PREDICTIONS_DIR, RESULTS_DIR, DOCS_DIR

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


def _load_upcoming():
    """Carica le previsioni per le partite non ancora giocate, un blocco per partita
    (l'ultima versione generata, nel caso la pipeline sia girata piu' volte sulla stessa partita).
    Ritorna (upcoming_df, match_order) oppure (None, None) se non ci sono dati."""
    pred_path = PREDICTIONS_DIR / "predictions_log.csv"
    if not pred_path.exists():
        return None, None

    preds = pd.read_csv(pred_path)
    if preds.empty:
        return None, None

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    preds["kickoff_dt"] = pd.to_datetime(preds["kickoff_utc"], utc=True, errors="coerce")
    upcoming = preds[preds["kickoff_dt"] >= now_utc].copy()
    upcoming = upcoming.sort_values("generated_utc").drop_duplicates(
        subset=["match_id", "market"], keep="last"
    )
    if upcoming.empty:
        return upcoming, []

    match_order = list(upcoming.groupby("match_id")["kickoff_dt"].min().sort_values().index)
    return upcoming, match_order


def _load_performance_summary():
    """Ritorna (n_graded, accuracy, avg_edge) oppure None se non c'e' ancora nulla di gradato."""
    grading_path = RESULTS_DIR / "results_grading.csv"
    if not grading_path.exists():
        return None
    graded = pd.read_csv(grading_path)
    if "correct" not in graded.columns:
        return None
    graded = graded.dropna(subset=["correct"])
    if graded.empty:
        return None
    return len(graded), graded["correct"].mean(), graded["estimated_edge"].mean()


def build_report():
    """Genera data/predictions/report_oggi.md (Markdown, si apre bene su GitHub)."""
    upcoming, match_order = _load_upcoming()
    if upcoming is None:
        print("Nessuna previsione ancora registrata: report non generato.")
        return

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

    perf = _load_performance_summary()
    if perf:
        n, accuracy, avg_edge = perf
        lines.append(
            f"**Finora:** {n} previsioni gia' concluse e verificate. "
            f"Accuratezza grezza: {accuracy*100:.1f}%. Edge medio stimato: "
            f"{avg_edge*100:.1f}%. Campione ancora piccolo, non e' un segnale affidabile."
        )
        lines.append("")

    if not match_order:
        lines.append("Nessuna partita in programma nelle prossime ore con previsioni disponibili.")
    else:
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
    n_matches = len(match_order) if match_order else 0
    print(f"-> report Markdown generato in {out_path} ({n_matches} partite)")


def _html_escape(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _edge_css_class(x):
    if pd.isna(x):
        return ""
    return "edge-pos" if x >= 0 else "edge-neg"


def build_html_report():
    """Genera data/predictions/report_oggi.html e la pubblica anche in docs/index.html
    (la cartella che GitHub Pages serve online)."""
    upcoming, match_order = _load_upcoming()

    generated_str = datetime.datetime.now(ROME).strftime("%d/%m/%Y alle %H:%M")

    perf_html = ""
    perf = _load_performance_summary()
    if perf:
        n, accuracy, avg_edge = perf
        perf_html = f"""
        <div class="perf">
          <strong>Finora:</strong> {n} previsioni già concluse e verificate —
          accuratezza grezza <strong>{accuracy*100:.1f}%</strong>,
          edge medio stimato <strong>{avg_edge*100:+.1f}%</strong>.
          Campione ancora piccolo, non è un segnale affidabile.
        </div>"""

    matches_html = ""
    if upcoming is None or not match_order:
        matches_html = '<p class="empty">Nessuna partita in programma nelle prossime ore con previsioni disponibili.</p>'
    else:
        cards = []
        for match_id in match_order:
            rows = upcoming[upcoming["match_id"] == match_id]
            first = rows.iloc[0]
            kickoff_rome = _to_rome(first["kickoff_utc"])
            kickoff_str = kickoff_rome.strftime("%a %d/%m — %H:%M") if kickoff_rome is not None else "-"

            row_html = []
            for _, r in rows.iterrows():
                label = MARKET_LABELS.get(r["market"], r["market"])
                edge_class = _edge_css_class(r["estimated_edge"])
                row_html.append(f"""
                <tr>
                  <td>{_html_escape(label)}</td>
                  <td>{_fmt_pct(r['model_probability'])}</td>
                  <td>{_fmt_odds(r['market_odds'])}</td>
                  <td>{_fmt_pct(r['market_implied_probability'])}</td>
                  <td class="{edge_class}">{_fmt_edge(r['estimated_edge'])}</td>
                </tr>""")

            extra = []
            if pd.notna(first.get("home_xg")) and pd.notna(first.get("away_xg")):
                extra.append(f"Gol attesi: {first['home_xg']:.2f} – {first['away_xg']:.2f}")
            if pd.notna(first.get("expected_corners")):
                extra.append(f"Corner attesi: {first['expected_corners']:.1f}")
            if pd.notna(first.get("expected_cards")):
                extra.append(f"Cartellini attesi: {first['expected_cards']:.1f}")
            extra_html = f'<div class="extra">{" · ".join(extra)}</div>' if extra else ""

            cards.append(f"""
      <section class="match-card">
        <div class="match-head">
          <h2>{_html_escape(first['home_team'])} <span class="vs">–</span> {_html_escape(first['away_team'])}</h2>
          <div class="meta">{_html_escape(first['competition'])} &nbsp;·&nbsp; {kickoff_str}</div>
        </div>
        <table>
          <thead>
            <tr><th>Mercato</th><th>Prob. modello</th><th>Quota</th><th>Prob. implicita</th><th>Edge</th></tr>
          </thead>
          <tbody>{''.join(row_html)}
          </tbody>
        </table>
        {extra_html}
      </section>""")
        matches_html = "\n".join(cards)

    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Previsioni — {generated_str}</title>
<style>
  :root {{
    --bg: #f7f7f5;
    --card-bg: #ffffff;
    --text: #1e1e1c;
    --text-muted: #6b6b66;
    --border: #e4e3de;
    --accent: #2f6f4f;
    --pos: #1f7a3f;
    --pos-bg: #eaf5ee;
    --neg: #a13a3a;
    --neg-bg: #fbeeee;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 32px 16px 64px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; }}
  h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
  .subtitle {{ color: var(--text-muted); font-size: 0.9rem; margin-bottom: 4px; }}
  .note {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 20px; }}
  .perf {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.9rem;
    margin-bottom: 24px;
  }}
  .match-card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 18px;
  }}
  .match-head h2 {{ font-size: 1.15rem; margin: 0 0 2px; font-weight: 600; }}
  .match-head .vs {{ color: var(--text-muted); font-weight: 400; }}
  .meta {{ color: var(--text-muted); font-size: 0.85rem; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th {{
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
  }}
  td {{ padding: 7px 8px; border-bottom: 1px solid var(--border); }}
  tbody tr:last-child td {{ border-bottom: none; }}
  .edge-pos {{ color: var(--pos); background: var(--pos-bg); font-weight: 600; border-radius: 4px; }}
  .edge-neg {{ color: var(--neg); background: var(--neg-bg); border-radius: 4px; }}
  .extra {{ margin-top: 10px; font-size: 0.82rem; color: var(--text-muted); }}
  .empty {{ color: var(--text-muted); }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #161614;
      --card-bg: #201f1c;
      --text: #ece9e4;
      --text-muted: #9a9890;
      --border: #35342f;
      --pos: #5fd189;
      --pos-bg: #17301f;
      --neg: #e08080;
      --neg-bg: #331b1b;
    }}
  }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Previsioni in programma</h1>
    <div class="subtitle">Generato il {generated_str} (ora italiana)</div>
    <div class="note">Sistema in fase di test/carta, nessuna scommessa reale. Le probabilità sono stime di un modello statistico (Poisson) basato sullo storico delle squadre, non certezze.</div>
    {perf_html}
    {matches_html}
  </div>
</body>
</html>
"""
    out_path = PREDICTIONS_DIR / "report_oggi.html"
    out_path.write_text(html, encoding="utf-8")

    # Copia anche in docs/index.html: e' la cartella che GitHub Pages pubblica online
    # (repo pubblico -> Settings -> Pages -> Source: Deploy from a branch -> main -> /docs).
    # .nojekyll disattiva l'elaborazione Jekyll di default di GitHub Pages, che qui non serve
    # (la pagina e' gia' HTML statico autosufficiente) ed evita comportamenti strani sui file.
    docs_index = DOCS_DIR / "index.html"
    docs_index.write_text(html, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    n_matches = len(match_order) if match_order else 0
    print(f"-> report HTML generato in {out_path} e pubblicato in {docs_index} ({n_matches} partite)")


if __name__ == "__main__":
    build_report()
    build_html_report()
