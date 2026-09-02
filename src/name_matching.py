"""Confronta i nomi delle squadre tra le diverse fonti dati (football-data.org usa nomi ufficiali
come 'AS Roma' o 'FC Internazionale Milano', football-data.co.uk usa nomi brevi come 'Roma' o 'Inter')
e trova la migliore corrispondenza, evitando falsi positivi pericolosi (es. Inter confuso con Milan,
o Atletico Madrid confuso con Real Madrid).
"""
import unicodedata
import difflib

_FILLERS = {
    "fc", "cf", "ac", "ss", "ssc", "us", "sc", "cd", "ud", "rc", "sv", "vfl", "vfb",
    "de", "the", "calcio", "football", "club", "1899",
}

_ALIASES = {
    frozenset(["inter"]): "Inter",
    frozenset(["internazionale"]): "Inter",
    frozenset(["athletic"]): "Ath Bilbao",
    frozenset(["atletico", "madrid"]): "Ath Madrid",
    frozenset(["paris", "saint", "germain"]): "Paris SG",
    frozenset(["borussia", "monchengladbach"]): "M'gladbach",
    frozenset(["koln"]): "FC Koln",
    frozenset(["espanyol"]): "Espanol",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _base_tokens(name: str):
    if not name:
        return []
    s = _strip_accents(name)
    s = s.replace(".", " ").replace("-", " ").replace("'", "")
    tokens = [t.lower() for t in s.split()]
    filtered = [t for t in tokens if t not in _FILLERS]
    return filtered if filtered else tokens


def _alias_match(name_tokens: set):
    best, best_len = None, 0
    for key, value in _ALIASES.items():
        if key.issubset(name_tokens) and len(key) > best_len:
            best, best_len = value, len(key)
    return best


def _token_subset_match(name_tokens: set, candidate_tokens: dict):
    matches = []
    for candidate, tokens in candidate_tokens.items():
        cand_set = set(tokens)
        if not cand_set or not name_tokens:
            continue
        if cand_set.issubset(name_tokens) or name_tokens.issubset(cand_set):
            overlap = len(cand_set & name_tokens)
            if overlap > 0:
                matches.append((candidate, overlap, len(cand_set)))
    if not matches:
        return None
    matches.sort(key=lambda m: (-m[1], m[2]))
    return matches[0][0]


def best_match(name: str, candidates, cutoff: float = 0.6):
    if not name or not candidates:
        return None

    name_tokens = set(_base_tokens(name))

    alias = _alias_match(name_tokens)
    if alias and alias in candidates:
        return alias

    candidate_tokens = {c: _base_tokens(c) for c in candidates}

    for c, tokens in candidate_tokens.items():
        if set(tokens) == name_tokens:
            return c

    subset_match = _token_subset_match(name_tokens, candidate_tokens)
    if subset_match:
        return subset_match

    norm_name = " ".join(sorted(name_tokens))
    norm_candidates = {c: " ".join(sorted(tokens)) for c, tokens in candidate_tokens.items()}
    close = difflib.get_close_matches(norm_name, list(norm_candidates.values()), n=1, cutoff=cutoff)
    if close:
        for c, nc in norm_candidates.items():
            if nc == close[0]:
                return c
    return None
