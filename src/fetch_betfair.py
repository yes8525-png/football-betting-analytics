"""Fase 2: volumi Betfair Exchange - il vero "flusso di soldi" (dati di mercato reali, non stime).

Login e Application Key richiedono le credenziali di un conto scommesse reale: vanno sempre
e solo messe come GitHub Actions secrets (BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD),
mai in chat con Claude. La Delayed Application Key e' gratuita e sufficiente per questo uso
(dati con qualche decina di secondi di ritardo, niente scommesse reali).

Versione con debug esplicito: ogni passaggio stampa qualcosa su stdout con flush=True,
cosi' se qualcosa si blocca o fallisce silenziosamente lo vediamo subito nel log.
"""
import sys
import traceback
import datetime
import requests
import pandas as pd

from config import BETFAIR_DIR, BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD, FIXTURES_DIR
import name_matching

# Il login e' specifico per giurisdizione: un conto .it (come il nostro) deve autenticarsi
# su identitysso.betfair.it, non su identitysso.betfair.com (quello e' per conti UK/globali,
# e infatti dava 403 Forbidden). L'endpoint di trading (api.betfair.com) invece resta lo stesso
# per tutte le giurisdizioni, cambia solo il login.
LOGIN_URL = "https://identitysso.betfair.it/api/login"
BETTING_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"


def _log(msg):
    print(f"[Betfair] {msg}", flush=True)


def is_configured() -> bool:
    return bool(BETFAIR_APP_KEY and BETFAIR_USERNAME and BETFAIR_PASSWORD)


def _login() -> str:
    headers = {
        "X-Application": BETFAIR_APP_KEY,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    resp = requests.post(LOGIN_URL, headers=headers,
                          data={"username": BETFAIR_USERNAME, "password": BETFAIR_PASSWORD}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("loginStatus") != "SUCCESS":
        raise RuntimeError(f"Login Betfair fallito: {data.get('loginStatus')}")
    return data["sessionToken"]


def _rpc(session_token: str, method: str, params: dict):
    headers = {
        "X-Application": BETFAIR_APP_KEY,
        "X-Authentication": session_token,
        "Content-Type": "application/json",
    }
    payload = {"jsonrpc": "2.0", "method": f"SportsAPING/v1.0/{method}", "params": params, "id": 1}
    resp = requests.post(BETTING_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        raise RuntimeError(f"Errore Betfair API ({method}): {body['error']}")
    return body["result"]


def _iso(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _list_soccer_markets(session_token: str):
    now = datetime.datetime.utcnow()
    end = now + datetime.timedelta(days=2)
    market_filter = {
        "eventTypeIds": ["1"],  # 1 = Soccer su Betfair
        "marketStartTime": {"from": _iso(now), "to": _iso(end)},
        "marketTypeCodes": ["MATCH_ODDS"],
    }
    return _rpc(session_token, "listMarketCatalogue", {
        "filter": market_filter,
        "marketProjection": ["EVENT", "RUNNER_DESCRIPTION"],
        "maxResults": "200",
    })


def _match_markets_to_fixtures(markets, fixtures: pd.DataFrame):
    """Abbina i mercati Betfair alle nostre fixture riusando lo stesso motore di name matching
    gia' usato per lo storico (src/name_matching.py)."""
    matched = []
    for m in markets:
        event_name = m.get("event", {}).get("name", "")
        if " v " not in event_name:
            continue
        home_bf, away_bf = [s.strip() for s in event_name.split(" v ", 1)]
        for _, fx in fixtures.iterrows():
            candidates = [fx["home_team"], fx["away_team"]]
            if name_matching.best_match(home_bf, candidates) and name_matching.best_match(away_bf, candidates):
                matched.append((m, fx))
                break
    return matched


def fetch_all():
    _log("fetch_all() avviato")

    if not is_configured():
        _log("secrets mancanti (BETFAIR_APP_KEY / BETFAIR_USERNAME / BETFAIR_PASSWORD): salto.")
        return
    _log("secrets presenti, procedo")

    fixtures_path = FIXTURES_DIR / "fixtures_master.csv"
    if not fixtures_path.exists():
        _log("nessuna fixture disponibile: salto Betfair.")
        return
    fixtures = pd.read_csv(fixtures_path)
    _log(f"{len(fixtures)} fixture caricate da fixtures_master.csv")

    try:
        _log("provo il login su Betfair...")
        session_token = _login()
        _log("login riuscito, ho un session token")
    except Exception as e:
        _log(f"LOGIN FALLITO: {type(e).__name__}: {e}")
        traceback.print_exc()
        return

    try:
        _log("chiedo la lista dei mercati Soccer (listMarketCatalogue)...")
        markets = _list_soccer_markets(session_token)
        _log(f"ricevuti {len(markets)} mercati da Betfair")
    except Exception as e:
        _log(f"ERRORE nel recupero mercati Betfair: {type(e).__name__}: {e}")
        traceback.print_exc()
        return

    matched = _match_markets_to_fixtures(markets, fixtures)
    _log(f"{len(matched)} mercati Betfair abbinati alle nostre fixture")
    if not matched:
        _log("nessun mercato abbinato: fine (non e' un errore, puo' dipendere dagli orari o dal name matching).")
        return

    market_ids = [m["marketId"] for m, _ in matched]
    try:
        _log("scarico prezzi/volumi (listMarketBook)...")
        books = _rpc(session_token, "listMarketBook", {
            "marketIds": market_ids,
            "priceProjection": {"priceData": ["EX_BEST_OFFERS"]},
        })
        _log(f"ricevuti {len(books)} market book")
    except Exception as e:
        _log(f"ERRORE nel recupero prezzi/volumi Betfair: {type(e).__name__}: {e}")
        traceback.print_exc()
        return
    books_by_id = {b["marketId"]: b for b in books}

    rows = []
    now_iso = datetime.datetime.utcnow().isoformat()
    for market, fx in matched:
        book = books_by_id.get(market["marketId"])
        if not book:
            continue
        runner_names = {r["selectionId"]: r.get("runnerName", "") for r in market.get("runners", [])}
        for runner in book.get("runners", []):
            ex = runner.get("ex", {})
            best_back = (ex.get("availableToBack") or [{}])[0].get("price")
            best_lay = (ex.get("availableToLay") or [{}])[0].get("price")
            rows.append({
                "snapshot_utc": now_iso,
                "match_id": fx["match_id"],
                "home_team": fx["home_team"],
                "away_team": fx["away_team"],
                "market_id": market["marketId"],
                "selection": runner_names.get(runner["selectionId"], runner["selectionId"]),
                "best_back_price": best_back,
                "best_lay_price": best_lay,
                "total_matched_selection": runner.get("totalMatched"),
                "total_matched_market": book.get("totalMatched"),
            })

    if not rows:
        _log("nessuna riga di volume costruita a partire dai market book.")
        return

    out = pd.DataFrame(rows)
    today = datetime.date.today().isoformat()
    out_path = BETFAIR_DIR / f"betfair_{today}.csv"
    out.to_csv(out_path, index=False)

    master_path = BETFAIR_DIR / "betfair_volume.csv"
    if master_path.exists():
        master = pd.read_csv(master_path)
        master = pd.concat([master, out], ignore_index=True)
    else:
        master = out
    master.to_csv(master_path, index=False)
    _log(f"-> {len(out)} righe di volume Betfair salvate in {out_path}")


if __name__ == "__main__":
    fetch_all()
