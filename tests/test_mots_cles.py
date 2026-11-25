import pytest

from catalogue_mobi.mots_cles import KeywordIndex, RuleIndex, normalize, split_keywords


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


def _rule_row(theme, sous_theme, termes, contexte_requis="", exclusions=""):
    return {
        "theme": theme,
        "sous_theme": sous_theme,
        "termes": termes,
        "contexte_requis": contexte_requis,
        "exclusions": exclusions,
    }


STATIONNEMENT = "stationnement ; parking ; horodateur"
RULE_ONTOLOGY = [
    _rule_row(
        "stationnement",
        "tarification",
        "tarification du stationnement ; tarif",
        STATIONNEMENT,
        "irve",
    ),
    _rule_row("stationnement", "voirie", "horodateur ; zone bleue", STATIONNEMENT),
    _rule_row("transport_collectif", "tarification", "tarif", "bus ; tram"),
    _rule_row("qualite_air", "qualite_de_l_air", "qualité de l'air ; PM2,5"),
    _rule_row("velo", "vls", "Vélo'v ; P+R", "velo"),
    _rule_row("contre_exemple", "faune_flore", "oiseaux"),
]


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            # mots de l'expression dans un autre ordre ; contexte trouvé
            "Stationnement : grille de tarification",
            [("stationnement/tarification", "tarification du stationnement", "stationnement", "")],
        ),
        (
            # « tarif » ne rattache au transport collectif qu'avec bus ou tram
            "Tarifs des parkings",
            [("stationnement/tarification", "tarif", "parking", "")],
        ),
        ("Tarifs 2024", []),  # terme sans contexte requis
        (
            # un terme qui est aussi dans le contexte suffit seul
            "Horodateurs de Grenoble",
            [("stationnement/voirie", "horodateur", "horodateur", "")],
        ),
        (
            # exclusion signalée, pas filtrée
            "Tarifs des bornes IRVE du parking",
            [("stationnement/tarification", "tarif", "parking", "irve")],
        ),
        (
            # sans contexte requis, le terme suffit ; virgule dans un terme
            "Concentrations PM2,5",
            [("qualite_air/qualite_de_l_air", "pm2,5", "", "")],
        ),
        (
            # apostrophe dans un mot ; « P+R » (mots d'une lettre) ignoré
            "Stations Vélo’v",
            [("velo/vls", "velov", "velo", "")],
        ),
        ("Parking P+R vélo par la rue", []),
        ("Recensement des oiseaux", []),  # contre-exemples ignorés
        ("", []),
    ],
    ids=[
        "expression_mots_dans_le_desordre",
        "contexte_requis",
        "sans_contexte",
        "terme_dans_le_contexte",
        "exclusion_signalee",
        "sans_contexte_requis_et_virgule",
        "apostrophe",
        "mots_d_une_lettre_ignores",
        "contre_exemple_ignore",
        "vide",
    ],
)
def test_rule_matches(text, expected):
    matches = RuleIndex(RULE_ONTOLOGY).matches("d1", text)

    found = [(m["ontology_id"], m["termes"], m["contexte"], m["exclus"]) for m in matches]
    assert found == expected
    assert all(m["dataset_id"] == "d1" for m in matches)
