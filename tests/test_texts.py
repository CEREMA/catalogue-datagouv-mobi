import pytest

from catalogue_mobi.constants import BGE_QUERY_INSTRUCTION
from catalogue_mobi.texts import (
    clean_description,
    dataset_text,
    archived_at,
    is_archived,
    ontology_text,
)


def _ontology_row(**overrides):
    row = {
        "theme": "elections",
        "theme_description": "Organisation et résultats des scrutins",
        "sous_theme": "procurations",
        "description": "Vote par procuration.",
        "mots_cles_indicatifs": "procuration",
    }
    return {**row, **overrides}


def _dataset_row(**overrides):
    row = {
        "id": "abc",
        "title": "Bureaux de vote",
        "description": "Liste des bureaux de vote de la commune.",
        "tags": "",
        "archived": "False",
    }
    return {**row, **overrides}


@pytest.mark.parametrize(
    "row, expected",
    [
        (
            _ontology_row(),
            BGE_QUERY_INSTRUCTION + "Organisation et résultats des scrutins. "
            "Vote par procuration. "
            "Mots-clés : procuration",
        ),
        (
            _ontology_row(mots_cles_indicatifs=""),
            BGE_QUERY_INSTRUCTION
            + "Organisation et résultats des scrutins. Vote par procuration.",
        ),
        (
            _ontology_row(description="  Vote par procuration  "),
            BGE_QUERY_INSTRUCTION + "Organisation et résultats des scrutins. "
            "Vote par procuration. "
            "Mots-clés : procuration",
        ),
        (
            _ontology_row(theme_description=None),
            BGE_QUERY_INSTRUCTION + "Vote par procuration. Mots-clés : procuration",
        ),
    ],
    ids=["complet", "sans_mots_cles", "espaces_superflus", "contre_exemple"],
)
def test_ontology_text(row, expected):
    assert ontology_text(row) == expected


@pytest.mark.parametrize(
    "row, expected",
    [
        (
            _dataset_row(),
            "Bureaux de vote\n\nListe des bureaux de vote de la commune.",
        ),
        (
            _dataset_row(tags="bureau-de-vote,elections"),
            "Bureaux de vote\n\n"
            "Liste des bureaux de vote de la commune.\n\n"
            "Mots-clés : bureau de vote, elections",
        ),
        (
            _dataset_row(description=""),
            "Bureaux de vote",
        ),
        (
            _dataset_row(description=None, tags=None),
            "Bureaux de vote",
        ),
    ],
    ids=["titre_description", "avec_tags", "sans_description", "valeurs_nulles"],
)
def test_dataset_text(row, expected):
    assert dataset_text(row) == expected


@pytest.mark.parametrize(
    "archived, expected",
    [
        ("False", False),
        ("", False),
        (None, False),
        ("2024-03-21T12:26:15.234000", True),
    ],
    ids=["false", "vide", "null", "date"],
)
def test_is_archived(archived, expected):
    assert is_archived(_dataset_row(archived=archived)) is expected


@pytest.mark.parametrize(
    "archived, expected",
    [
        ("False", None),
        ("", None),
        (None, None),
        (" 2024-03-21T12:26:15.234000 ", "2024-03-21T12:26:15.234000"),
    ],
    ids=["false", "vide", "null", "date"],
)
def test_archived_at(archived, expected):
    assert archived_at(_dataset_row(archived=archived)) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Texte simple.", "Texte simple."),
        ("<p>Un <b>paragraphe</b>.</p>", "Un paragraphe ."),
        ("**gras** et *italique* et _souligné_ et `code`", "gras et italique et souligné et code"),
        ("# Titre\n\nDu texte.", "Titre Du texte."),
        ("[data.gouv](https://data.gouv.fr)", "data.gouv"),
        ("![alt text](image.png)", "alt text"),
        ("- item 1\n- item 2", "item 1 item 2"),
        ("> une citation", "une citation"),
        ("---\ntexte après", "texte après"),
        ("Espaces   multiples", "Espaces multiples"),
        ("Trop\n\n\n\nde sauts", "Trop de sauts"),
        ("Entité &amp; encodée", "Entité & encodée"),
        ("Azur\\ en partenariat", "Azur en partenariat"),
        ("", ""),
        (None, ""),
    ],
    ids=[
        "texte_simple",
        "html",
        "emphase_markdown",
        "titre_markdown",
        "lien_markdown",
        "image_markdown",
        "liste_markdown",
        "citation_markdown",
        "separateur_markdown",
        "espaces_multiples",
        "sauts_de_ligne_multiples",
        "entite_html",
        "retour_ligne_explicite",
        "vide",
        "none",
    ],
)
def test_clean_description(text, expected):
    assert clean_description(text) == expected
