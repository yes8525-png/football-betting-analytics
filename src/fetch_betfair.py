"""Fase 2 - non ancora attiva.

L'autenticazione Betfair richiede username + password + Application Key insieme (login "interattivo"
via identitysso.betfair.com), non solo una API key come le altre fonti. Sono credenziali di un vero
conto scommesse, quindi vanno gestite con più cautela delle altre: solo come GitHub Actions secrets,
mai incollate in chat.

Questo modulo e' uno scheletro: si attiva quando BETFAIR_APP_KEY / BETFAIR_USERNAME / BETFAIR_PASSWORD
sono presenti come secrets. Finche' non lo sono, la pipeline salta questo step senza fallire.
"""
import sys
from config import BETFAIR_APP_KEY, BETFAIR_USERNAME, BETFAIR_PASSWORD, BETFAIR_DIR

LOGIN_URL = "https://identitysso.betfair.com/api/login"
BETTING_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"


def is_configured() -> bool:
    return bool(BETFAIR_APP_KEY and BETFAIR_USERNAME and BETFAIR_PASSWORD)


def fetch_all():
    if not is_configured():
        print("! Betfair non configurato (Fase 2): salto il recupero volumi.", file=sys.stderr)
        return
    # TODO (Fase 2): login interattivo, poi listMarketBook per ottenere back/lay price e volumi
    # scambiati sui mercati 1X2 / Over-Under delle partite del giorno, salvare in data/betfair/.
    raise NotImplementedError("Integrazione Betfair da completare in Fase 2.")


if __name__ == "__main__":
    fetch_all()
