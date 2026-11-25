"""Rattachement par mots-clés (logique pure) : baseline de la méthode
historique (`KeywordIndex`) et méthode par règles (`RuleIndex`, plus bas).

Reproduit la recherche du client (old/pipelinecomplet.ipynb) : un jeu est
rattaché à un thème si l'un des « mots-clés du thème » apparaît dans son
titre, sa description ou ses tags, sans casse ni accents, en début de mot,
avec jusqu'à deux lettres de plus (pluriels : « comptage » trouve
« comptages »). Seul écart : les tirets sont lus comme des espaces, pour que
le tag « trafic-routier » corresponde au mot-clé « trafic routier ».

En plus, la même recherche est faite au niveau du sous-thème avec ses
mots-clés indicatifs (prévue mais non branchée dans la méthode historique).
Les contre-exemples, propres aux embeddings, sont ignorés.
"""

import re
import unicodedata
from collections import defaultdict
from typing import Iterable

CONTRE_EXEMPLE = "contre_exemple"


def normalize(text: str | None) -> str:
    """Minuscules, sans accents, tirets remplacés par des espaces."""
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.replace("-", " ")


def split_keywords(cell: str | None) -> list[str]:
    """Mots-clés normalisés d'une cellule séparée par des virgules."""
    return [k for k in (normalize(p).strip() for p in (cell or "").split(",")) if k]


def _pattern(keyword: str) -> str:
    """Le mot-clé suivi d'au plus deux lettres, puis une fin de mot."""
    return rf"{re.escape(keyword)}[a-z]{{0,2}}\b"


class KeywordFinder:
    """Trouve tous les mots-clés présents dans un texte, y compris ceux qui
    se chevauchent (« comptage » dans « comptage et flux », « flux » aussi).

    Une seule expression pour tous les mots-clés, essayée à chaque début de
    mot ; à une position donnée, elle renvoie le plus long, et les mots-clés
    qui en sont des préfixes sont vérifiés à la même position."""

    def __init__(self, keywords: Iterable[str]):
        keywords = sorted(set(keywords), key=lambda k: (-len(k), k))
        alternatives = "|".join(re.escape(k) for k in keywords)
        self._regex = (
            re.compile(rf"\b(?=({alternatives})[a-z]{{0,2}}\b)") if keywords else None
        )
        # mot-clé -> [(mot-clé plus court qui en est un préfixe, son expression)]
        self._prefixes = {
            k: [(p, re.compile(_pattern(p))) for p in keywords if p != k and k.startswith(p)]
            for k in keywords
        }

    def find(self, text: str) -> set[str]:
        found = set()
        if self._regex is None:
            return found
        for m in self._regex.finditer(text):
            keyword = m.group(1)
            found.add(keyword)
            for prefix, regex in self._prefixes[keyword]:
                if regex.match(text, m.start()):
                    found.add(prefix)
        return found


class KeywordIndex:
    """Mots-clés de l'ontologie, au niveau du thème et du sous-thème."""

    def __init__(self, ontology_rows: Iterable[dict]):
        self.themes: dict[str, set[str]] = defaultdict(set)  # mot -> thèmes
        self.sous_themes: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for row in ontology_rows:
            theme = row["theme"]
            if theme == CONTRE_EXEMPLE:
                continue
            for k in split_keywords(row.get("mots_cles_theme")):
                self.themes[k].add(theme)
            ontology_id = f"{theme}/{row['sous_theme']}"
            for k in split_keywords(row.get("mots_cles_indicatifs")):
                self.sous_themes[k].add((theme, ontology_id))
        self._theme_finder = KeywordFinder(self.themes)
        self._sous_theme_finder = KeywordFinder(self.sous_themes)

    def matches(self, dataset_id: str, text: str) -> list[dict]:
        """Un rattachement par thème et par sous-thème trouvés, avec les
        mots-clés qui l'ont déclenché (`ontology_id` vide au niveau thème)."""
        text = normalize(text)
        by_target: dict[tuple[str, str | None], set[str]] = defaultdict(set)
        for keyword in self._theme_finder.find(text):
            for theme in self.themes[keyword]:
                by_target[(theme, None)].add(keyword)
        for keyword in self._sous_theme_finder.find(text):
            for theme, ontology_id in self.sous_themes[keyword]:
                by_target[(theme, ontology_id)].add(keyword)
        return [
            {
                "dataset_id": dataset_id,
                "theme": theme,
                "ontology_id": ontology_id,
                "keywords": ", ".join(sorted(keywords)),
            }
            for (theme, ontology_id), keywords in sorted(
                by_target.items(), key=lambda item: (item[0][0], item[0][1] or "")
            )
        ]


# Mots vides ignorés dans un terme (« places de stationnement »), en plus des
# mots d'une lettre (« P+R », « Vélo'v » avant fusion)
STOPWORDS = frozenset("au aux de des du en et la le les ou par pour sur un une".split())

# Séparateur des colonnes de règles : celui du tableau source, dont des termes
# contiennent des virgules (« PM2,5 »)
RULE_SEPARATOR = ";"


def rule_normalize(text: str | None) -> str:
    """`normalize`, et apostrophe supprimée à l'intérieur d'un mot de plus de
    deux lettres (« Vélo'v » -> « velov ») ; gardée après une élision
    (« d'arrêt » reste deux mots)."""
    text = normalize(text).replace("\u2019", "'")
    return re.sub(r"(?<=[a-z]{3})'(?=[a-z])", "", text)


def _terms(cell: str | None) -> list[tuple[str, frozenset[str]]]:
    """(terme, ses mots significatifs) pour chaque terme d'une cellule."""
    terms = {}
    for part in (cell or "").split(RULE_SEPARATOR):
        term = rule_normalize(part).strip()
        words = frozenset(w for w in re.findall(r"[a-z0-9]+", term) if len(w) > 1)
        words -= STOPWORDS
        if words and term not in terms:
            terms[term] = words
    return list(terms.items())


class RuleIndex:
    """Rattachement par règles, par sous-thème (colonnes séparées par « ; ») :

    - un terme est trouvé si tous ses mots sont dans le texte, dans
      n'importe quel ordre (même règle de mot que la baseline) ;
    - un terme (`termes`) rattache si un mot du `contexte_requis` est aussi
      trouvé, lui-même compris ; sans contexte requis, il suffit seul ;
    - les `exclusions` trouvées sont signalées, sans rien filtrer : la règle
      métier se décide dans Grist.
    """

    def __init__(self, ontology_rows: Iterable[dict]):
        self._sous_themes = []
        words: set[str] = set()
        for row in ontology_rows:
            if row["theme"] == CONTRE_EXEMPLE:
                continue
            columns = [_terms(row.get(c)) for c in ("termes", "contexte_requis", "exclusions")]
            words.update(w for terms in columns for _, ws in terms for w in ws)
            self._sous_themes.append((f"{row['theme']}/{row['sous_theme']}", *columns))
        self._finder = KeywordFinder(words)

    def matches(self, dataset_id: str, text: str) -> list[dict]:
        """Un rattachement par sous-thème trouvé, avec les termes et le
        contexte qui l'ont déclenché et les exclusions présentes."""
        found = self._finder.find(rule_normalize(text))

        def present(terms):
            return sorted(t for t, ws in terms if ws <= found)

        result = []
        for ontology_id, termes, contexte, exclusions in self._sous_themes:
            termes_found = present(termes)
            if not termes_found:
                continue
            contexte_found = present(contexte)
            if contexte and not contexte_found:
                continue
            result.append(
                {
                    "dataset_id": dataset_id,
                    "ontology_id": ontology_id,
                    "termes": "; ".join(termes_found),
                    "contexte": "; ".join(contexte_found),
                    "exclus": "; ".join(present(exclusions)),
                }
            )
        return sorted(result, key=lambda m: m["ontology_id"])
