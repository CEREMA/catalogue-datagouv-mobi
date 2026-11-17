import pytest

from catalogue_mobi.mots_cles import KeywordIndex, normalize, split_keywords


def _row(theme, sous_theme, mots_cles_theme="", mots_cles_indicatifs=""):
    return {
        "theme": theme,
        "sous_theme": sous_theme,
        "mots_cles_theme": mots_cles_theme,
        "mots_cles_indicatifs": mots_cles_indicatifs,
    }


ONTOLOGY = [
    _row("trafic_routier", "historique", "Trafic routier, comptages", "comptage, comptage et flux"),
    _row("trafic_routier", "temps_reel", "Trafic routier, comptages", "temps reel"),
    _row("velo", "comptages", "Vélo", "comptage, compteurs velo"),
    _row("contre_exemple", "faune_flore", "", "oiseaux, comptage"),
]


def test_normalize():
    assert normalize("Vélos en Libre-Service") == "velos en libre service"
    assert normalize(None) == ""


def test_split_keywords():
    assert split_keywords(" Trafic routier,  , Vélo ") == ["trafic routier", "velo"]
    assert split_keywords(None) == []


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "Comptages routiers 2024. Mots-clés : trafic-routier",
            [
                ("trafic_routier", None, "comptages, trafic routier"),
                ("trafic_routier", "trafic_routier/historique", "comptage"),
                ("velo", "velo/comptages", "comptage"),
            ],
        ),
        (
            # « comptages » (thème) ne trouve pas le singulier ; « comptage »
            # est trouvé aussi à l'intérieur de « comptage et flux »
            "Données de comptage et flux",
            [
                ("trafic_routier", "trafic_routier/historique", "comptage, comptage et flux"),
                ("velo", "velo/comptages", "comptage"),
            ],
        ),
        ("Itinéraires VÉLO", [("velo", None, "velo")]),
        ("Vélodrome municipal", []),  # « velo » + 5 lettres : pas un mot-clé
        ("Recensement des oiseaux", []),  # contre-exemples ignorés
        ("", []),
    ],
    ids=[
        "theme_et_sous_themes",
        "mots_cles_imbriques",
        "casse_et_accents",
        "debut_de_mot_seulement",
        "contre_exemple_ignore",
        "vide",
    ],
)
def test_matches(text, expected):
    matches = KeywordIndex(ONTOLOGY).matches("d1", text)

    assert [(m["theme"], m["ontology_id"], m["keywords"]) for m in matches] == expected
    assert all(m["dataset_id"] == "d1" for m in matches)
