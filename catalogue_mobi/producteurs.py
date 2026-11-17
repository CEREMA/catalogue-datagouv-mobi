"""Type de producteur déduit de la catégorie juridique INSEE (logique pure).

Le SIREN (9 premiers chiffres du `business_number_id` de l'export des
organisations data.gouv.fr, souvent un SIRET) donne la catégorie juridique
INSEE de l'organisation : commune, département, intercommunalité, service de
l'État, association...
"""

# Niveau de collectivité, par catégorie juridique INSEE (niveau III).
# Seules les collectivités territoriales et les EPCI à fiscalité propre ont un
# niveau : syndicats, pôles métropolitains, etc. n'en ont pas.
NIVEAUX = {
    "7210": "Commune",
    "7220": "Département",
    "7230": "Région",
    "7225": "Collectivité à statut particulier",  # outre-mer
    "7229": "Collectivité à statut particulier",  # Paris, Corse, Lyon, Martinique...
    "7343": "Intercommunalité",  # communauté urbaine
    "7344": "Intercommunalité",  # métropole
    "7346": "Intercommunalité",  # communauté de communes
    "7348": "Intercommunalité",  # communauté d'agglomération
}

ECONOMIE_MIXTE = ("5415", "5515", "5615")

PUBLIC_LOCAL = "Public local"
PUBLIC_NATIONAL = "Public national"
NON_PUBLIC = "Non public"


def siren(business_number_id: str | None) -> str | None:
    """SIREN (9 chiffres) d'un SIRET ou d'un SIREN, None s'il n'y en a pas."""
    if not isinstance(business_number_id, str):
        return None
    chiffres = "".join(c for c in business_number_id if c.isdigit())
    return chiffres[:9] if len(chiffres) >= 9 else None


def _code(nature_juridique) -> str | None:
    code = str(nature_juridique or "").strip()
    return code if code[:1].isdigit() else None


def _public_local(code: str) -> bool:
    return code.startswith(("72", "4140")) or (
        code.startswith("73") and not code.startswith("738")
    )


def _public_national(code: str) -> bool:
    return code.startswith(("71", "738", "74", "41"))


def niveau(nature_juridique) -> str | None:
    """Niveau de collectivité territoriale, None pour les autres organisations."""
    return NIVEAUX.get(_code(nature_juridique) or "")


def type_producteur(nature_juridique) -> str | None:
    """Public local (collectivités et leurs établissements), public national
    (État et ses établissements, autres organismes publics), non public
    sinon. None si la catégorie est inconnue."""
    code = _code(nature_juridique)
    if code is None:
        return None
    if _public_local(code):
        return PUBLIC_LOCAL
    if _public_national(code):
        return PUBLIC_NATIONAL
    return NON_PUBLIC


def badges_acceptes(nature_juridique) -> str | None:
    """Badges data.gouv.fr cohérents avec la catégorie juridique (séparés par
    une virgule), ou None si la catégorie est inconnue ou sans équivalent.

    data.gouv.fr réserve le badge « autorité locale » aux collectivités et aux
    intercommunalités à fiscalité propre ; les autres organismes publics
    locaux (syndicats, SDIS, CCAS...) peuvent porter l'un ou l'autre badge
    public.
    """
    code = _code(nature_juridique)
    # Organisation internationale, sociétés d'économie mixte : pas de badge attendu
    if code is None or code.startswith("3") or code in ECONOMIE_MIXTE:
        return None
    if niveau(code):
        return PUBLIC_LOCAL
    if _public_local(code):
        return f"{PUBLIC_LOCAL},{PUBLIC_NATIONAL}"
    if _public_national(code):
        return PUBLIC_NATIONAL
    return NON_PUBLIC


def famille(nature_juridique) -> str | None:
    """Grande famille de la catégorie juridique INSEE."""
    code = _code(nature_juridique)
    if code is None:
        return None
    if code.startswith("71"):
        return "État"
    if code.startswith("72"):
        return "Collectivité territoriale"
    if code.startswith("738"):
        return "Établissement public national"
    if code.startswith("73"):
        return "Établissement public local"
    if code.startswith("74"):
        return "Autre organisme public"
    if code.startswith("4"):
        return "Établissement public industriel et commercial"
    if code.startswith("9"):
        return "Association ou fondation"
    return "Entreprise ou organisme privé"


def classification(nature_juridique) -> dict:
    """Colonnes dérivées de la catégorie juridique, stockées avec le SIREN."""
    return {
        "famille": famille(nature_juridique),
        "niveau": niveau(nature_juridique),
        "type_producteur": type_producteur(nature_juridique),
        "badges_acceptes": badges_acceptes(nature_juridique),
    }
