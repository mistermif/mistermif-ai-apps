from __future__ import annotations

import re


STOP_TERMS = (
    "area di sosta",
    "aree di sosta",
    "sosta camper",
    "sosta caravan",
    "parcheggio camper",
    "parcheggio caravan",
    "park4night",
    "park for night",
)


def is_stopover_search(message: str) -> bool:
    """Return True for requests to find caravan/camper stopovers."""
    normalized = message.casefold()
    if any(term in normalized for term in STOP_TERMS):
        return True
    return (
        any(term in normalized for term in ("area", "aree", "parcheggio", "sosta"))
        and any(term in normalized for term in ("camper", "caravan", "gratuit"))
    )


def extract_radius_km(message: str) -> int | None:
    """Extract a 1–200 km search radius from a natural-language reply."""
    normalized = message.casefold().replace(",", ".")
    patterns = (
        r"(?:raggio|entro|nel raggio di)\s*(?:di\s*)?(\d+(?:\.\d+)?)\s*(km|chilometr[oi]|metri?|m)\b",
        r"(?:raggio|entro|nel raggio di)\s*(?:di\s*)?(\d+(?:\.\d+)?)\b",
        r"\b(\d+(?:\.\d+)?)\s*(km|chilometr[oi]|metri?|m)\b",
        r"^\s*(\d+(?:\.\d+)?)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        value = float(match.group(1))
        unit = match.group(2) if match.lastindex and match.lastindex >= 2 else "km"
        if unit.startswith("m") and unit != "miglia":
            value /= 1000
        return max(1, min(200, round(value)))
    return None


def build_stopover_prompt(
    original_request: str,
    radius_km: int,
    latitude: float,
    longitude: float,
) -> str:
    """Build the grounded-search request used after local validation."""
    return (
        "RICERCA SOSTE GEOLOCALIZZATA. "
        f"Richiesta originale dell'utente: {original_request!r}. "
        f"Partenza GPS: {latitude:.6f}, {longitude:.6f}. "
        f"Cerca entro {radius_km} km aree di sosta o parcheggi adatti a camper/caravan, "
        "privilegiando le opzioni gratuite. Consulta risultati pubblici aggiornati e "
        "includi le pagine pubbliche di Park4night quando disponibili, senza aggirare "
        "login o abbonamenti. Ordina obbligatoriamente le proposte dalla più vicina alla "
        "più lontana. Per ciascuna indica nome, località, distanza stimata dal GPS, costo, "
        "tipo di sosta, possibilità di pernottamento se verificabile, limitazioni utili e "
        "link della fonte. Distingui un parcheggio da un campeggio e marca chiaramente ciò "
        "che va verificato. Non fare una lezione sul campeggio libero: segnala solo i vincoli "
        "specifici e pertinenti alle singole proposte."
    )
