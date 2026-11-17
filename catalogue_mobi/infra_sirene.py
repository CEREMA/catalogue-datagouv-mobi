"""Nom et catégorie juridique d'un SIREN (API Recherche d'entreprises), et
libellé INSEE d'une catégorie juridique (API Métadonnées). Sans clé."""

import time
import urllib.parse
from datetime import date

from catalogue_mobi.constants import INSEE_CJ_API_URL, SIRENE_API_URL, SIRENE_DELAY
from catalogue_mobi.infra_http import get_json


def lookup_siren(numero: str) -> dict:
    """Nom et catégorie juridique d'un SIREN ; valeurs vides s'il est
    introuvable (il reste en cache pour ne pas être réinterrogé)."""
    query = urllib.parse.urlencode({"q": numero, "per_page": 1})
    resultats = get_json(f"{SIRENE_API_URL}?{query}", not_found={})
    trouve = next(
        (r for r in resultats.get("results", []) if r.get("siren") == numero), None
    )
    return {
        "siren": numero,
        "nom_sirene": (trouve or {}).get("nom_complet") or "",
        "nature_juridique": (trouve or {}).get("nature_juridique") or "",
        "interroge_le": date.today().isoformat(),
    }


def lookup_sirens(numeros: list[str]) -> list[dict]:
    resultats = []
    for i, numero in enumerate(numeros, 1):
        resultats.append(lookup_siren(numero))
        if i % 50 == 0:
            print(f"{i} / {len(numeros)} SIREN interrogés")
        time.sleep(SIRENE_DELAY)
    return resultats


def lookup_legal_categories(codes: list[str]) -> dict[str, str]:
    """Intitulé INSEE de chaque catégorie juridique (niveau III), vide si
    inconnue."""
    libelles = {}
    for code in codes:
        reponse = get_json(f"{INSEE_CJ_API_URL}/{code}", not_found={})
        libelles[code] = reponse.get("intitule") or ""
        time.sleep(SIRENE_DELAY)
    return libelles
