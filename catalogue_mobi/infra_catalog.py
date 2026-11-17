"""Téléchargement des derniers exports du catalogue data.gouv.fr.

Les exports sont republiés chaque nuit comme ressources du jeu « Catalogue
des données de data.gouv.fr », sous un nom daté
(export-dataset-20261117-055149.csv). Ils sont enregistrés sous un nom stable
dans data/catalog/, en écrasant les précédents.
"""

from pathlib import Path

from catalogue_mobi.constants import CATALOG_API_URL, CATALOG_DIR, CATALOG_EXPORTS
from catalogue_mobi.infra_http import download, get_json


def latest_export_urls(resources: list[dict]) -> dict[str, str]:
    """URL de la dernière version de chaque export suivi, par nom de fichier
    local, à partir des ressources du jeu catalogue."""
    urls = {}
    for prefix, filename in CATALOG_EXPORTS.items():
        candidates = [
            r
            for r in resources
            if (r.get("title") or "").startswith(prefix + "-")
            and (r.get("format") or "").lower() == "csv"
        ]
        if not candidates:
            raise RuntimeError(f"Export {prefix} introuvable dans {CATALOG_API_URL}")
        # le titre est daté : le plus grand est le plus récent
        urls[filename] = max(candidates, key=lambda r: r["title"])["url"]
    return urls


def fetch_catalog(directory: Path = CATALOG_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for filename, url in latest_export_urls(get_json(CATALOG_API_URL)["resources"]).items():
        print(f"Téléchargement de {url}")
        download(url, directory / filename)
