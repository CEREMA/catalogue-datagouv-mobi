"""Construction des textes à embedder (logique métier pure)."""

import html
import re

from catalogue_mobi.constants import BGE_QUERY_INSTRUCTION

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MD_HEADER_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MD_BLOCKQUOTE_RE = re.compile(r"^>\s?", re.MULTILINE)
_MD_LIST_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_MD_HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE)
_MD_EMPHASIS_RE = re.compile(r"(\*\*|\*|__|_|`)")
_MD_LINE_BREAK_RE = re.compile(r"\\+")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_description(text: str) -> str:
    """Retire le markdown/HTML d'une description data.gouv et l'aplatit sur
    une seule ligne.

    Balises, liens, emphases et sauts de ligne n'apportent aucun signal
    sémantique et diluent l'embedding sur les descriptions longues (cf.
    README "Modèle") : on garde le texte des liens/images, on jette le reste.
    """
    if not text:
        return ""
    text = html.unescape(text)
    text = _MD_IMAGE_RE.sub(r"\1", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _MD_HEADER_RE.sub("", text)
    text = _MD_BLOCKQUOTE_RE.sub("", text)
    text = _MD_LIST_BULLET_RE.sub("", text)
    text = _MD_HR_RE.sub("", text)
    text = _MD_EMPHASIS_RE.sub("", text)
    text = _MD_LINE_BREAK_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def ontology_text(row: dict) -> str:
    """Texte d'un sous-thème : description du thème, du sous-thème, mots-clés.

    Préfixé de l'instruction BGE côté requête (voir README "Modèle") : ce
    texte joue le rôle de requête courte face aux jeux de données, longs.
    """
    parts = [_clean(row["theme_description"]), _clean(row["description"])]
    text = " ".join(_with_final_dot(p) for p in parts if p)
    keywords = _clean(row["mots_cles_indicatifs"])
    if keywords:
        text += f" Mots-clés : {keywords}"
    return BGE_QUERY_INSTRUCTION + text


def _with_final_dot(text: str) -> str:
    return text if text.endswith(".") else text + "."


def dataset_text(row: dict) -> str:
    """Texte d'un jeu de données : titre, description (nettoyée du
    markdown/HTML), tags. Le titre est en tête pour survivre à la troncature."""
    parts = [_clean(row["title"]), clean_description(_clean(row["description"]))]
    tags = [t.replace("-", " ") for t in _clean(row["tags"]).split(",") if t]
    if tags:
        parts.append("Mots-clés : " + ", ".join(tags))
    return "\n\n".join(p for p in parts if p)


def is_archived(row: dict) -> bool:
    """La colonne `archived` vaut "False" / vide, ou la date d'archivage."""
    return _clean(row["archived"]) not in ("", "False")


def archived_at(row: dict) -> str | None:
    """Date d'archivage du jeu de données, ou None s'il n'est pas archivé."""
    return _clean(row["archived"]) if is_archived(row) else None
