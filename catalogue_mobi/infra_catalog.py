"""Téléchargement des exports quotidiens du catalogue data.gouv.fr.

Les exports sont publiés chaque nuit comme ressources du jeu « Catalogue des
données de data.gouv.fr », sous un nom daté (export-dataset-20261117-055149.csv).
Ils sont enregistrés sous un nom stable dans data/catalog/, et l'URL de chaque
fichier est notée dans manifest.json : un export déjà à jour n'est pas
retéléchargé.
"""

import json
from pathlib import Path

from catalogue_mobi.constants import (
    CATALOG_API_URL,
    CATALOG_DIR,
    CATALOG_EXPORTS,
    CATALOG_MANIFEST,
)
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


def _read_manifest(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def fetch_catalog(directory: Path = CATALOG_DIR, force: bool = False) -> list[str]:
    """Télécharge les exports qui ont changé. Retourne les fichiers mis à jour."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / CATALOG_MANIFEST.name
    manifest = _read_manifest(manifest_path)
    urls = latest_export_urls(get_json(CATALOG_API_URL)["resources"])

    updated = []
    for filename, url in urls.items():
        dest = directory / filename
        if not force and dest.exists() and manifest.get(filename) == url:
            print(f"{filename} déjà à jour")
            continue
        print(f"Téléchargement de {url}")
        download(url, dest)
        manifest[filename] = url
        manifest_path.write_text(json.dumps(manifest, indent=2))
        updated.append(filename)
    return updated
