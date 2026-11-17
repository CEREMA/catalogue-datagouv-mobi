"""Appels HTTP (bibliothèque standard), avec reprise sur erreur passagère."""

import http.client
import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

from catalogue_mobi.constants import USER_AGENT

RETRIES = 6


def _request(url: str, accept: str = "application/json") -> urllib.request.Request:
    return urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": accept}
    )


def get_json(url: str, not_found=None):
    """JSON renvoyé par `url`, ou `not_found` sur 404/410. Les erreurs
    passagères (429, 5xx, coupure réseau) sont retentées avec une attente
    croissante."""
    for essai in range(RETRIES):
        try:
            with urllib.request.urlopen(_request(url), timeout=30) as reponse:
                return json.load(reponse)
        except urllib.error.HTTPError as erreur:
            if erreur.code in (404, 410):
                return not_found
            if erreur.code != 429 and erreur.code < 500:
                raise
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            ConnectionError,
        ):
            pass
        time.sleep(2**essai)
    raise RuntimeError(f"API injoignable : {url}")


def download(url: str, dest: Path) -> None:
    """Télécharge `url` dans `dest`, via un fichier temporaire : une
    interruption ne laisse jamais de fichier tronqué sous le nom final.

    Le serveur coupe parfois la connexion en cours de route sans erreur
    (fichiers de plus d'1 Go) : la taille reçue est comparée à
    `Content-Length` et le téléchargement reprend là où il s'est arrêté
    (requête `Range`)."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.unlink(missing_ok=True)
    expected = None
    for essai in range(RETRIES):
        done = tmp.stat().st_size if tmp.exists() else 0
        request = _request(url, accept="*/*")
        if done:
            request.add_header("Range", f"bytes={done}-")
        try:
            with urllib.request.urlopen(request, timeout=120) as reponse:
                if done and reponse.status != 206:
                    raise RuntimeError(f"Reprise refusée par le serveur : {url}")
                if expected is None:
                    expected = int(reponse.headers["Content-Length"]) + done
                with open(tmp, "ab") as f:
                    shutil.copyfileobj(reponse, f, length=1024 * 1024)
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            ConnectionError,
        ):
            pass
        size = tmp.stat().st_size if tmp.exists() else 0
        if expected is not None and size == expected:
            tmp.replace(dest)
            return
        print(f"Téléchargement interrompu ({size} / {expected} octets), reprise...")
        time.sleep(2**essai)
    raise RuntimeError(f"Téléchargement incomplet : {url}")
