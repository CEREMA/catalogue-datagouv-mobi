import pytest

from catalogue_mobi.producteurs import (
    badges_acceptes,
    classification,
    famille,
    niveau,
    siren,
    type_producteur,
)


@pytest.mark.parametrize(
    "business_number_id, expected",
    [
        ("13001831000010", "130018310"),  # SIRET
        ("130018310", "130018310"),  # SIREN
        ("130 018 310", "130018310"),
        ("1234", None),
        ("", None),
        (None, None),
    ],
    ids=["siret", "siren", "espaces", "trop_court", "vide", "none"],
)
def test_siren(business_number_id, expected):
    assert siren(business_number_id) == expected


@pytest.mark.parametrize(
    "code, type_, famille_, niveau_, badges",
    [
        ("7210", "Public local", "Collectivité territoriale", "Commune", "Public local"),
        ("7344", "Public local", "Établissement public local", "Intercommunalité",
         "Public local"),
        ("7354", "Public local", "Établissement public local", None,
         "Public local,Public national"),  # syndicat mixte
        ("7120", "Public national", "État", None, "Public national"),
        ("7389", "Public national", "Établissement public national", None,
         "Public national"),  # ex. Cerema
        ("5710", "Non public", "Entreprise ou organisme privé", None, "Non public"),
        ("5515", "Non public", "Entreprise ou organisme privé", None, None),  # SEM
        ("9220", "Non public", "Association ou fondation", None, "Non public"),
        ("", None, None, None, None),
        (None, None, None, None, None),
    ],
)
def test_classification(code, type_, famille_, niveau_, badges):
    assert type_producteur(code) == type_
    assert famille(code) == famille_
    assert niveau(code) == niveau_
    assert badges_acceptes(code) == badges
    assert classification(code) == {
        "famille": famille_,
        "niveau": niveau_,
        "type_producteur": type_,
        "badges_acceptes": badges,
    }
