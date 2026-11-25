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


def _rule_row(theme, sous_theme, mots_cles_theme, discriminants, contextuels, exclus=""):
    return {
        "theme": theme,
        "sous_theme": sous_theme,
        "mots_cles_theme": mots_cles_theme,
        "mots_cles_discriminants": discriminants,
        "mots_cles_contextuels": contextuels,
        "mots_exclus": exclus,
    }


RULE_ONTOLOGY = [
    _rule_row(
        "stationnement",
        "tarification",
        "Stationnement, Parking",
        "tarification stationnement, forfait post stationnement",
        "tarification, tarif",
    ),
    _rule_row(
        "stationnement",
        "voirie",
        "Stationnement, Parking",
        "zone bleue",
        "stationnement",
    ),
    _rule_row(
        "transport_collectif", "tarification", "bus, tram", "billettique", "tarif"
    ),
    _rule_row("velo", "comptages", "Vélo", "compteurs velo", "comptage", "oiseaux"),
    _rule_row("contre_exemple", "faune_flore", "", "oiseaux", ""),
]


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            # les mots de l'expression, dans un autre ordre et non contigus
            "Stationnement : grille de tarification",
            [
                (
                    "stationnement/tarification",
                    "tarification stationnement",
                    "tarification (+ stationnement)",
                    "",
                )
            ],
        ),
        (
            # contextuel validé par un mot-clé du thème ; « tarif » ne
            # rattache pas au transport collectif sans « bus » ni « tram »
            "Tarifs des parkings",
            [("stationnement/tarification", "", "tarif (+ parking)", "")],
        ),
        ("Tarifs 2024", []),  # contextuel seul
        (
            # un contextuel ne se valide pas lui-même : « stationnement » est
            # aussi mot-clé du thème
            "Stationnement des oiseaux",
            [],
        ),
        (
            "Places en zone bleue, stationnement",
            [("stationnement/voirie", "zone bleue", "", "")],
        ),
        (
            # mot exclu signalé, pas filtré ; contre-exemples ignorés
            "Comptage des oiseaux à vélo",
            [("velo/comptages", "", "comptage (+ velo)", "oiseaux")],
        ),
        (
            "Forfait post-stationnement",
            [("stationnement/tarification", "forfait post stationnement", "", "")],
        ),
        ("", []),
    ],
    ids=[
        "expression_mots_dans_le_desordre",
        "contextuel_valide_par_le_theme",
        "contextuel_seul",
        "contextuel_ne_se_valide_pas_lui_meme",
        "discriminant_seul",
        "mot_exclu_signale",
        "tirets",
        "vide",
    ],
)
def test_rule_matches(text, expected):
    matches = RuleIndex(RULE_ONTOLOGY).matches("d1", text)

    assert [
        (m["ontology_id"], m["discriminants"], m["contextuels"], m["exclus"])
        for m in matches
    ] == expected
    assert all(m["dataset_id"] == "d1" for m in matches)
